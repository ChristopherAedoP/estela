"""Recorder: control de grabación con OBS y subida/escritura de la nota.

Responsabilidades separadas:
- start()/stop(): solo controlan OBS y devuelven la ruta del .mka.
- upload_and_write(): sube al servidor (encendiendo la VM si hace falta) y escribe
  la nota en la carpeta de actas. Lo usa la cola de procesamiento.

La lógica es independiente de Qt (testeable).
"""
from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from typing import Callable

import httpx

from .config import Config
from .obs_client import ObsClient
from .log import get_logger
from . import infra


log = get_logger()

ProgressCb = Callable[[str, str], None]  # (state, detail)


class RecorderError(Exception):
    """Fallo transitorio (red/servidor): se puede reintentar."""


class PermanentError(RecorderError):
    """Fallo permanente (grabación vacía/corrupta): NO reintentar."""


class Recorder:
    def __init__(self, cfg: Config, on_progress: ProgressCb | None = None):
        self.cfg = cfg
        self._on_progress = on_progress or (lambda s, d: None)
        self._recording = False
        # URL del servidor efectivo resuelto para el trabajo en curso (NAS o local).
        self._effective_url: str | None = None

    @property
    def recording(self) -> bool:
        return self._recording

    def _emit(self, state: str, detail: str = "") -> None:
        self._on_progress(state, detail)

    # --- control de grabación (solo OBS) ---

    def start(self) -> None:
        if self._recording:
            return
        self._emit("starting", "Iniciando OBS…")
        if not infra.ensure_obs(self.cfg):
            raise RecorderError("No se pudo iniciar OBS / WebSocket (puerto 4455).")
        with ObsClient(self.cfg.obs_url, self.cfg.obs_password) as obs:
            if self.cfg.audio_device_id and self.cfg.audio_device_id != "default":
                obs.set_device(self.cfg.obs_input_name, self.cfg.audio_device_id)
            # Ganancia para compensar salidas HDMI/NVIDIA de bajo nivel
            obs.set_gain(self.cfg.obs_input_name, self.cfg.audio_gain_db)
            obs.start_record()
        self._recording = True
        self._emit("recording", "Grabando")
        log.info("grabación iniciada")

    def stop(self) -> Path:
        """Detiene OBS y devuelve la ruta del archivo grabado (sin subir)."""
        if not self._recording:
            raise RecorderError("No hay grabación en curso.")
        self._emit("stopping", "Deteniendo grabación…")
        if not infra.ensure_obs(self.cfg):
            raise RecorderError("OBS no responde para detener.")
        with ObsClient(self.cfg.obs_url, self.cfg.obs_password) as obs:
            path = obs.stop_record()
        self._recording = False
        log.info("stop_record -> %r", path)

        rec = Path(path) if path else None
        if not rec or not rec.exists():
            log.error("archivo de OBS no encontrado: %r", path)
            raise RecorderError("No se encontró el archivo grabado de OBS.")

        self._wait_file_released(rec)
        return rec

    # --- subida / nota (lo usa la cola) ---

    def upload_and_write(
        self, recording: Path, title: str, on_progress: ProgressCb | None = None
    ) -> Path:
        """Sube la grabación (encendiendo la VM si hace falta) y escribe la nota.

        Lanza RecorderError si falla (la cola decide reintentar). NO encola nada:
        la persistencia/reintentos los gestiona la ProcessingQueue.
        """
        emit = on_progress or self._on_progress
        recording = Path(recording)
        if not recording.exists():
            raise PermanentError(f"No existe la grabación: {recording}")
        size = recording.stat().st_size
        log.info("procesando '%s' (%d bytes) titulo=%r", recording.name, size, title)
        if size < 1024:
            raise PermanentError(
                "La grabación está vacía (0 bytes). Revisa la salida de audio elegida "
                "y graba al menos unos segundos."
            )

        self._ensure_server(emit)

        emit("uploading", "Transcribiendo… (puede tardar)")
        note_path = self._upload(recording, title)
        emit("done", f"Acta lista: {note_path.name}")
        log.info("acta generada: %s", note_path)
        return note_path

    def _ensure_server(self, emit: ProgressCb) -> None:
        """Resuelve el servidor efectivo (cascada NAS -> local) y lo fija.

        Lanza RecorderError si ningún servidor (primario ni local) queda disponible.
        """
        url = infra.resolve_server(self.cfg, emit=emit)
        if not url:
            raise RecorderError(
                "Ningún servidor disponible: el principal no responde y no se pudo "
                "usar el servidor local."
            )
        self._effective_url = url
        log.info("servidor efectivo: %s", url)

    def _upload(self, recording: Path, title: str) -> Path:
        server_url = self._effective_url or self.cfg.server_url
        log.info("subiendo a %s/transcribe", server_url)
        # Leer los bytes completos: pasar un file handle a httpx con archivos grandes
        # puede provocar "Too much data for declared Content-Length" si el tamaño
        # difiere entre el cálculo y el envío. Con bytes, httpx fija bien el length.
        audio_bytes = recording.read_bytes()
        files = {"audio": (recording.name, audio_bytes, "application/octet-stream")}
        data = {"title": title}
        with httpx.Client(timeout=1800) as client:
            r = client.post(
                f"{server_url}/transcribe", files=files, data=data
            )
            r.raise_for_status()
            resp = r.json()

        note_path = self._unique_note_path(resp["filename"])
        note_path.write_text(resp["markdown"], encoding="utf-8")
        return note_path

    def _unique_note_path(self, filename: str) -> Path:
        """Evita sobrescribir: si ya existe, añade sufijo _2, _3, …"""
        base = self.cfg.actas_path() / filename
        if not base.exists():
            return base
        stem = base.stem
        suffix = base.suffix
        n = 2
        while True:
            candidate = base.with_name(f"{stem}_{n}{suffix}")
            if not candidate.exists():
                return candidate
            n += 1

    # --- utilidades ---

    @staticmethod
    def _wait_file_released(path: Path, attempts: int = 50) -> None:
        """Espera a que OBS termine de escribir: archivo accesible Y tamaño estable >0.

        Con grabaciones muy cortas OBS puede tardar en volcar el buffer/índice mka;
        si no se espera, el archivo queda en 0 bytes.
        """
        last_size = -1
        stable = 0
        for _ in range(attempts):
            try:
                size = path.stat().st_size
                # comprobar que se puede abrir (no bloqueado por OBS)
                with open(path, "rb"):
                    pass
                if size > 0 and size == last_size:
                    stable += 1
                    if stable >= 2:  # tamaño estable en 2 lecturas seguidas
                        return
                else:
                    stable = 0
                last_size = size
            except OSError:
                stable = 0
            time.sleep(0.3)
