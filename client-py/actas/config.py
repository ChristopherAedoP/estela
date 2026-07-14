"""Configuración persistente del cliente Actas.

Se guarda en un JSON dentro del directorio de datos del usuario (multiplataforma).
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, asdict, field
from pathlib import Path


def _data_dir() -> Path:
    """Directorio de datos de la app, por plataforma."""
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        base = str(Path.home() / "Library" / "Application Support")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    d = Path(base) / "Actas"
    d.mkdir(parents=True, exist_ok=True)
    return d


DATA_DIR = _data_dir()
CONFIG_PATH = DATA_DIR / "config.json"
PENDING_PATH = DATA_DIR / "pending.json"  # cola legada (se migra a queue.json)
QUEUE_PATH = DATA_DIR / "queue.json"
LOG_PATH = DATA_DIR / "actas.log"


@dataclass
class Config:
    """Configuración del cliente.

    Los valores NO se hardcodean en el código: los defaults son neutros y la
    configuración real (servidor, vault, OBS, etc.) la introduce el usuario desde
    la ventana de Ajustes; se persiste en `config.json` del directorio de datos.
    """
    # Servidor de transcripción primario (FastAPI). Configurar en Ajustes.
    # Cascada de resolución: primario -> (encender VM) -> local -> (arrancar local).
    server_url: str = "http://localhost:8770"
    # Servidor local de respaldo. Si el primario no responde, se usa este.
    local_server_url: str = "http://localhost:8770"
    # Arrancar el servidor local (Ollama + actas-server) automáticamente cuando el
    # primario no responde y el local tampoco está corriendo.
    auto_start_local: bool = False
    # Rutas para arrancar el servidor local (solo se usan si auto_start_local=True).
    # Directorio del server (contiene .venv, .env y el paquete app).
    local_server_dir: str = ""
    # Python del venv del server local (por defecto: <local_server_dir>/.venv).
    local_server_python: str = ""
    # URL de Ollama local (se arranca si no responde antes del server local).
    local_ollama_url: str = "http://127.0.0.1:11434"
    # Vault Obsidian (destino de las notas). Vacío => configurar en Ajustes.
    vault_path: str = ""
    # Carpeta donde guardar las actas. Si es relativa, se resuelve dentro del vault.
    actas_dir: str = "Actas"
    # Host Proxmox para encender la VM (opcional). Configurar en Ajustes.
    proxmox_host: str = ""
    vm_id: str = ""
    auto_start_vm: bool = False
    # OBS (obs-websocket). El password se genera en OBS y se pone en Ajustes.
    obs_url: str = "ws://127.0.0.1:4455"
    obs_password: str = ""
    obs_exe: str = r"C:\Program Files\obs-studio\bin\64bit\obs64.exe"
    obs_input_name: str = "Audio Escritorio (Actas)"
    audio_device_id: str = "default"  # device_id de la salida a grabar
    audio_device_label: str = "Por defecto"
    # Ganancia de audio en dB aplicada a la captura (las salidas HDMI/NVIDIA, como
    # los parlantes de un monitor, se capturan a nivel muy bajo; +20dB lo compensa)
    audio_gain_db: float = 20.0
    # Carpeta donde OBS guarda las grabaciones
    recordings_dir: str = str(Path.home() / "Videos" / "estela-rec")
    # Comportamiento
    ask_title: bool = True
    default_title: str = "Reunión"
    # Borrar la grabación local tras subirla con éxito (el audio queda en el servidor)
    delete_local_after_upload: bool = True

    def actas_path(self) -> Path:
        """Carpeta destino de las actas (crea si no existe).

        Si `actas_dir` es absoluta se usa tal cual; si es relativa, se resuelve
        dentro del vault. Vacía => directamente el vault.
        """
        sub = (self.actas_dir or "").strip()
        if not sub:
            target = Path(self.vault_path)
        else:
            p = Path(sub)
            target = p if p.is_absolute() else Path(self.vault_path) / p
        target.mkdir(parents=True, exist_ok=True)
        return target

    @classmethod
    def load(cls) -> "Config":
        if CONFIG_PATH.exists():
            try:
                data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
                known = {f for f in cls.__dataclass_fields__}
                return cls(**{k: v for k, v in data.items() if k in known})
            except Exception:
                pass
        cfg = cls()
        cfg.save()
        return cfg

    def save(self) -> None:
        CONFIG_PATH.write_text(
            json.dumps(asdict(self), indent=2, ensure_ascii=False), encoding="utf-8"
        )
