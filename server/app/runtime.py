"""Comprobaciones del entorno de ejecucion: dispositivo de inferencia y Ollama.

torch se importa DENTRO de las funciones a proposito. Importarlo al cargar el
modulo anadiria varios segundos al arranque del servidor y ataria el arranque a
que la pila de CUDA cargue correctamente.
"""
import logging

from app.config import config

logger = logging.getLogger("actas.runtime")


def cuda_available() -> bool:
    """True si torch ve una GPU CUDA utilizable."""
    try:
        import torch

        return bool(torch.cuda.is_available())
    except Exception:
        logger.warning("No se pudo consultar CUDA; se asume CPU", exc_info=True)
        return False


def resolve_device_compute() -> tuple[str, str]:
    """Devuelve (device, compute_type) para faster-whisper.

    Con los valores por defecto ("auto") se detecta el dispositivo: CUDA si esta
    disponible y CPU en caso contrario. El tipo de computo acompana al
    dispositivo, porque float16 en CPU no esta soportado y obliga a CTranslate2 a
    degradar de forma silenciosa.

    Un valor explicito en ACTAS_WHISPER_DEVICE o ACTAS_WHISPER_COMPUTE siempre
    manda sobre la deteccion.
    """
    device = (config.whisper_device or "auto").strip().lower()
    compute = (config.whisper_compute or "auto").strip().lower()

    if device == "auto":
        device = "cuda" if cuda_available() else "cpu"
    if compute == "auto":
        compute = "float16" if device == "cuda" else "int8"

    return device, compute


def whisper_uses_cuda() -> bool:
    """True si la transcripcion va a competir por la VRAM con el LLM."""
    device, _ = resolve_device_compute()
    return device == "cuda"


def pipeline_status() -> tuple[bool, dict]:
    """Verifica que las dependencias pesadas de la transcripcion se pueden importar.

    Es la comprobacion que /health barato NO hace. Un fallo aqui (tipicamente el
    de OpenBLAS al importar torch) es exactamente el caso en que el servidor
    responde 'ok' y luego devuelve 500 en /transcribe.
    """
    detail: dict = {}
    try:
        import torch  # noqa: F401
    except BaseException as e:  # noqa: BLE001
        # BaseException a proposito: el fallo de OpenBLAS puede abortar de formas
        # que no derivan de Exception.
        detail.update(torch=False, error=f"torch: {e}")
        return False, detail
    detail["torch"] = True

    try:
        import faster_whisper  # noqa: F401
    except BaseException as e:  # noqa: BLE001
        detail.update(faster_whisper=False, error=f"faster_whisper: {e}")
        return False, detail
    detail["faster_whisper"] = True

    device, compute = resolve_device_compute()
    detail.update(device=device, compute=compute)
    return True, detail


def ollama_status() -> tuple[bool, dict]:
    """Comprueba que Ollama responde y que el modelo configurado esta descargado.

    Devuelve (listo, detalle). `listo` es False tanto si Ollama no responde como
    si responde pero no tiene el modelo: en ambos casos el acta saldra sin
    resumen.
    """
    import httpx

    detail: dict = {"url": config.ollama_url, "model": config.ollama_model}
    try:
        with httpx.Client(timeout=3) as client:
            r = client.get(f"{config.ollama_url}/api/tags")
            r.raise_for_status()
            names = [m.get("name", "") for m in r.json().get("models", [])]
    except Exception as e:
        detail.update(reachable=False, error=str(e))
        return False, detail

    present = config.ollama_model in names
    detail.update(reachable=True, model_present=present)
    return present, detail
