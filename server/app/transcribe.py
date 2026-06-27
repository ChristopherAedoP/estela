import re

from app.models import Segment
from app.config import config


def _is_degenerate(text: str) -> bool:
    """Detecta texto alucinado por repetición típico de Whisper.

    Ej: 'y Árbol, y Árbol, y Árbol...' o 'el bing el bing el bing...'.
    """
    t = text.strip()
    if not t:
        return True
    words = re.findall(r"\w+", t.lower())
    if len(words) >= 6:
        unique_ratio = len(set(words)) / len(words)
        if unique_ratio < 0.30:  # muy pocas palabras distintas = loop
            return True
    # frase corta repetida muchas veces (ej "el bing el bing el bing")
    tokens = t.lower().split()
    if len(tokens) >= 8:
        # busca el patrón más repetido de 1-3 palabras
        for size in (1, 2, 3):
            chunks = [" ".join(tokens[i:i + size]) for i in range(0, len(tokens) - size + 1, size)]
            if chunks:
                most = max(set(chunks), key=chunks.count)
                if chunks.count(most) / len(chunks) > 0.6:
                    return True
    return False


def segments_from_whisper(raw_segments) -> list[Segment]:
    """Convierte segmentos crudos de faster-whisper en Segment limpios.

    Descarta segmentos degenerados (alucinaciones de repetición de Whisper).
    """
    out = []
    for s in raw_segments:
        text = s.text.strip()
        if _is_degenerate(text):
            continue
        out.append(Segment(start=float(s.start), end=float(s.end), text=text))
    return out


def transcribe(audio_path: str):
    """Carga el modelo, transcribe y libera. Devuelve (lista[Segment], duracion_seg)."""
    from faster_whisper import WhisperModel

    # Parámetros anti-alucinación comunes (sin lo del VAD)
    common = dict(
        language=config.language,
        condition_on_previous_text=False,   # evita loops por contexto previo (clave)
        compression_ratio_threshold=2.4,    # descarta segmentos con texto repetitivo
        no_speech_threshold=0.6,            # descarta tramos sin habla real
        repetition_penalty=1.1,             # penaliza repeticiones en la generación
        no_repeat_ngram_size=3,             # prohíbe repetir n-gramas de 3
    )

    model = WhisperModel(
        config.whisper_model,
        device=config.whisper_device,
        compute_type=config.whisper_compute,
    )
    try:
        # 1er intento: con VAD (filtra silencios, reduce alucinaciones).
        segments_iter, info = model.transcribe(
            audio_path,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 500},
            **common,
        )
        segments = segments_from_whisper(segments_iter)
        duration = info.duration

        # El VAD a veces descarta TODO el audio (voces con música/efectos de fondo,
        # ganancia aplicada, etc.) y devuelve 0 segmentos aunque haya voz clara.
        # Fallback: reintentar SIN VAD para no perder la transcripción.
        if not segments:
            segments_iter, info = model.transcribe(
                audio_path, vad_filter=False, **common
            )
            segments = segments_from_whisper(segments_iter)
            duration = info.duration
    finally:
        del model
        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass
    return segments, duration
