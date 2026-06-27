import httpx
from app.config import config

PROMPT_TEMPLATE = """Eres un asistente que redacta actas de reunión en español.
A partir de la siguiente transcripción, genera EXACTAMENTE estas secciones markdown,
sin añadir nada antes ni después:

## Resumen
(2-3 párrafos)

## Puntos clave
- ...

## Decisiones
- ...

## Tareas
- [ ] (responsable si se infiere) descripción

Transcripción:
{transcript}
"""


def build_prompt(transcript: str) -> str:
    return PROMPT_TEMPLATE.format(transcript=transcript)


def _call_ollama(prompt: str) -> str:
    url = f"{config.ollama_url}/api/generate"
    payload = {
        "model": config.ollama_model,
        "prompt": prompt,
        "stream": False,
        # Desactiva el "thinking" de modelos que lo soportan (qwen3, gemma4).
        # Parametro nativo de la API de Ollama; los modelos sin thinking lo ignoran.
        # Reemplaza al antiguo truco de appendear "/no_think" al prompt.
        "think": False,
    }
    with httpx.Client(timeout=600) as client:
        r = client.post(url, json=payload)
        r.raise_for_status()
        return r.json().get("response", "")


def parse_summary(raw: str) -> str:
    idx = raw.find("## Resumen")
    return raw[idx:].strip() if idx != -1 else raw.strip()


def summarize(transcript: str):
    """Devuelve (markdown_block | None, ok: bool)."""
    try:
        raw = _call_ollama(build_prompt(transcript))
        return parse_summary(raw), True
    except Exception:
        return None, False
