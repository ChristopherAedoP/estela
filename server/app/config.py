import os
from dataclasses import dataclass
from typing import Optional


def _opt_int(name: str) -> Optional[int]:
    val = os.getenv(name, "").strip()
    if not val:
        return None
    try:
        return int(val)
    except ValueError:
        return None


@dataclass
class Config:
    whisper_model: str = os.getenv("ACTAS_WHISPER_MODEL", "large-v3")
    whisper_device: str = os.getenv("ACTAS_WHISPER_DEVICE", "cuda")
    whisper_compute: str = os.getenv("ACTAS_WHISPER_COMPUTE", "float16")
    language: str = os.getenv("ACTAS_LANGUAGE", "es")
    ollama_url: str = os.getenv("ACTAS_OLLAMA_URL", "http://127.0.0.1:11434")
    ollama_model: str = os.getenv("ACTAS_OLLAMA_MODEL", "gemma4:12b-it-qat")
    hf_token: str = os.getenv("ACTAS_HF_TOKEN", "")
    audio_dir: str = os.getenv("ACTAS_AUDIO_DIR", "/mnt/actas/audio")
    tmp_dir: str = os.getenv("ACTAS_TMP_DIR", "/tmp/actas")
    # Acotar nº de hablantes en la diarización (None = sin límite, comportamiento actual)
    max_speakers: Optional[int] = _opt_int("ACTAS_MAX_SPEAKERS")
    min_speakers: Optional[int] = _opt_int("ACTAS_MIN_SPEAKERS")


config = Config()
