"""Cola de procesamiento en background (FIFO, 1 a la vez).

Desacopla grabar de procesar: al detener una grabación se *encola* el trabajo y la
app vuelve a idle inmediatamente. Un QThread persistente consume la cola en orden,
sube cada audio al servidor y escribe la nota. Los fallos quedan en la cola y se
reintentan automáticamente cuando el servidor vuelve a responder.

Persistencia en queue.json para no perder trabajos si se cierra la app.
"""
from __future__ import annotations

import json
import threading
import time
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal

from .config import Config, QUEUE_PATH, PENDING_PATH
from .recorder import Recorder, RecorderError, PermanentError
from .log import get_logger
from . import infra

log = get_logger()

# Estados de un trabajo
QUEUED = "queued"
PROCESSING = "processing"
FAILED = "failed"


@dataclass
class Job:
    id: str
    recording: str
    title: str
    state: str = QUEUED
    error: str = ""
    ts: str = ""

    @staticmethod
    def new(recording: str, title: str) -> "Job":
        return Job(
            id=uuid.uuid4().hex[:8],
            recording=str(recording),
            title=title,
            state=QUEUED,
            ts=datetime.now().isoformat(timespec="seconds"),
        )


@dataclass
class Counts:
    queued: int = 0
    processing: int = 0
    failed: int = 0

    @property
    def active(self) -> int:
        return self.queued + self.processing


class ProcessingQueue(QObject):
    """Gestiona la cola y un worker thread persistente."""

    job_started = Signal(str)            # title
    job_done = Signal(str, str)          # title, note_name
    job_failed = Signal(str, str)        # title, error
    queue_changed = Signal(int, int, int)  # queued, processing, failed (tipos simples)
    progress = Signal(str)               # detalle para tooltip

    RETRY_INTERVAL = 30.0                # s entre reintentos automáticos de fallidos

    def __init__(self, cfg: Config):
        super().__init__()
        self.cfg = cfg
        self._lock = threading.RLock()
        self._jobs: list[Job] = []
        self._wake = threading.Event()
        self._stop = False
        self._thread = QThread()
        self.moveToThread(self._thread)
        self._thread.started.connect(self._run)
        self._load()

    # --- API pública (thread-safe) ---

    def start(self) -> None:
        self._thread.start()

    def shutdown(self) -> None:
        self._stop = True
        self._wake.set()
        self._thread.quit()
        self._thread.wait(3000)

    def enqueue(self, recording: str, title: str) -> None:
        with self._lock:
            self._jobs.append(Job.new(recording, title))
            self._save()
        log.info("encolado: %s", title)
        self._emit_counts()
        self._wake.set()

    def retry_failed(self) -> None:
        """Marca los fallidos como queued para reintentar ya."""
        with self._lock:
            for j in self._jobs:
                if j.state == FAILED:
                    j.state = QUEUED
                    j.error = ""
            self._save()
        self._emit_counts()
        self._wake.set()

    def counts(self) -> Counts:
        with self._lock:
            c = Counts()
            for j in self._jobs:
                if j.state == QUEUED:
                    c.queued += 1
                elif j.state == PROCESSING:
                    c.processing += 1
                elif j.state == FAILED:
                    c.failed += 1
            return c

    # --- worker loop ---

    def _run(self) -> None:
        log.info("worker de cola iniciado")
        last_retry = 0.0
        while not self._stop:
            try:
                job = self._next_queued()
                if job is None:
                    now = time.time()
                    if now - last_retry >= self.RETRY_INTERVAL and self._has_failed():
                        last_retry = now
                        if infra.server_healthy(self.cfg):
                            log.info("reintentando fallidos automáticamente")
                            self.retry_failed()
                            continue
                    self._wake.wait(timeout=5.0)
                    self._wake.clear()
                    continue

                self._process_job(job)
            except Exception:
                # El worker NUNCA debe morir: loguear y seguir
                log.exception("error en el loop del worker de cola")
                time.sleep(2.0)
        log.info("worker de cola detenido")

    def _process_job(self, job: Job) -> None:
        self._set_state(job, PROCESSING)
        self.job_started.emit(job.title)
        self._emit_counts()
        recorder = Recorder(self.cfg, on_progress=lambda s, d: self.progress.emit(d))
        try:
            note = recorder.upload_and_write(Path(job.recording), job.title)
            self._remove(job)
            self._cleanup_recording(job.recording)
            self.job_done.emit(job.title, note.name)
            log.info("job done: %s -> %s", job.title, note.name)
        except PermanentError as e:
            # Fallo permanente (grabación vacía/corrupta): descartar, NO reintentar
            self._remove(job)
            self._cleanup_recording(job.recording)
            self.job_failed.emit(job.title, str(e))
            log.warning("job descartado (permanente): %s (%s)", job.title, e)
        except RecorderError as e:
            self._set_state(job, FAILED, str(e))
            self.job_failed.emit(job.title, str(e))
            log.warning("job failed (reintentable): %s (%s)", job.title, e)
        except Exception as e:  # pragma: no cover
            self._set_state(job, FAILED, f"Error inesperado: {e}")
            self.job_failed.emit(job.title, str(e))
            log.exception("job error inesperado: %s", job.title)
        self._emit_counts()

    # --- helpers internos ---

    def _cleanup_recording(self, recording: str) -> None:
        """Borra el .mka local tras procesarlo (el audio queda archivado en el NAS)."""
        if not self.cfg.delete_local_after_upload:
            return
        try:
            p = Path(recording)
            if p.exists():
                p.unlink()
                log.info("grabacion local borrada: %s", p.name)
        except Exception:
            log.exception("no se pudo borrar la grabacion local: %s", recording)

    def _next_queued(self) -> Job | None:
        with self._lock:
            for j in self._jobs:
                if j.state == QUEUED:
                    return j
            return None

    def _has_failed(self) -> bool:
        with self._lock:
            return any(j.state == FAILED for j in self._jobs)

    def _set_state(self, job: Job, state: str, error: str = "") -> None:
        with self._lock:
            job.state = state
            job.error = error
            self._save()

    def _remove(self, job: Job) -> None:
        with self._lock:
            self._jobs = [j for j in self._jobs if j.id != job.id]
            self._save()

    def _emit_counts(self) -> None:
        c = self.counts()
        self.queue_changed.emit(c.queued, c.processing, c.failed)

    # --- persistencia ---

    def _load(self) -> None:
        items: list[dict] = []
        if QUEUE_PATH.exists():
            try:
                items = json.loads(QUEUE_PATH.read_text(encoding="utf-8"))
            except Exception:
                items = []
        elif PENDING_PATH.exists():
            # migración del formato legado: items con {recording, title, ts}
            try:
                old = json.loads(PENDING_PATH.read_text(encoding="utf-8"))
                for it in old:
                    items.append({
                        "id": uuid.uuid4().hex[:8],
                        "recording": it.get("recording", ""),
                        "title": it.get("title", "Reunión"),
                        "state": QUEUED,
                        "error": "",
                        "ts": it.get("ts", ""),
                    })
                log.info("migrados %d items de pending.json", len(items))
            except Exception:
                items = []

        with self._lock:
            self._jobs = []
            for it in items:
                try:
                    job = Job(**{k: it.get(k, "") for k in Job.__dataclass_fields__})
                    # cualquier 'processing' interrumpido vuelve a queued
                    if job.state == PROCESSING:
                        job.state = QUEUED
                    self._jobs.append(job)
                except Exception:
                    continue
            self._save()
        # limpiar el legado tras migrar
        try:
            if PENDING_PATH.exists():
                PENDING_PATH.unlink()
        except Exception:
            pass

    def _save(self) -> None:
        data = [asdict(j) for j in self._jobs]
        try:
            QUEUE_PATH.write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception:
            log.exception("no se pudo guardar la cola")
