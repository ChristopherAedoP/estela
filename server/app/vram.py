"""Gestión de VRAM: descarga modelos de Ollama para dejar sitio a Whisper/pyannote.

En la RTX 3060 (12 GB) el LLM (gemma4:12b-it-qat ~9 GB, o qwen3:8b ~10.6 GB) y
whisper large-v3 (~3 GB) NO caben simultáneamente. El pipeline debe liberar Ollama
antes de cargar Whisper y dejar que Ollama recargue el modelo al resumir.
"""
import httpx
from app.config import config


def unload_ollama_model() -> bool:
    """Pide a Ollama descargar el modelo de la VRAM (keep_alive=0).

    Devuelve True si la petición se hizo OK, False si Ollama no responde
    (no es fatal: si Ollama está caído tampoco ocupa VRAM).
    """
    url = f"{config.ollama_url}/api/generate"
    payload = {"model": config.ollama_model, "keep_alive": 0}
    try:
        with httpx.Client(timeout=30) as client:
            r = client.post(url, json=payload, timeout=30)
            r.raise_for_status()
        return True
    except Exception:
        return False


def free_torch_cache() -> None:
    """Libera la caché de CUDA de torch si está disponible."""
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
    except Exception:
        pass
