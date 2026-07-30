import os
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


def _opt_int(name: str) -> Optional[int]:
    val = os.getenv(name, "").strip()
    if not val:
        return None
    try:
        return int(val)
    except ValueError:
        return None


def _default_data_dir() -> Path:
    """Directorio de datos del servidor, por plataforma.

    Se usa solo como valor por defecto: ACTAS_AUDIO_DIR sigue mandando. Antes el
    default era /mnt/actas/audio, una ruta que solo existe en el despliegue del
    autor y que en cualquier otra maquina hace fallar el archivado con
    PermissionError, ya que archive_audio crea el directorio en cada peticion.

    No se crea aqui: importar la configuracion no debe tocar el sistema de
    archivos.
    """
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    elif sys.platform == "darwin":
        base = str(Path.home() / "Library" / "Application Support")
    else:
        base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / "estela"


@dataclass
class Config:
    whisper_model: str = os.getenv("ACTAS_WHISPER_MODEL", "large-v3")
    # "auto" resuelve a cuda/float16 si hay GPU, y a cpu/int8 si no. Un valor
    # explicito manda. La resolucion vive en app.runtime para no importar torch aqui.
    whisper_device: str = os.getenv("ACTAS_WHISPER_DEVICE", "auto")
    whisper_compute: str = os.getenv("ACTAS_WHISPER_COMPUTE", "auto")
    language: str = os.getenv("ACTAS_LANGUAGE", "es")
    ollama_url: str = os.getenv("ACTAS_OLLAMA_URL", "http://127.0.0.1:11434")
    ollama_model: str = os.getenv("ACTAS_OLLAMA_MODEL", "gemma4:12b-it-qat")
    hf_token: str = os.getenv("ACTAS_HF_TOKEN", "")
    audio_dir: str = os.getenv("ACTAS_AUDIO_DIR", "").strip() or str(
        _default_data_dir() / "audio"
    )
    tmp_dir: str = os.getenv("ACTAS_TMP_DIR", "").strip() or str(
        Path(tempfile.gettempdir()) / "estela"
    )
    # Acotar nº de hablantes en la diarización (None = sin límite, comportamiento actual)
    max_speakers: Optional[int] = _opt_int("ACTAS_MAX_SPEAKERS")
    min_speakers: Optional[int] = _opt_int("ACTAS_MIN_SPEAKERS")


config = Config()
