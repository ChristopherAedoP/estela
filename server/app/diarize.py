import logging
from app.models import SpeakerTurn
from app.config import config

logger = logging.getLogger("actas.diarize")

_SPEAKER_MAP: dict[str, str] = {}


def _label_to_name(label: str) -> str:
    if label not in _SPEAKER_MAP:
        _SPEAKER_MAP[label] = f"Hablante {len(_SPEAKER_MAP) + 1}"
    return _SPEAKER_MAP[label]


def turns_from_annotation(annotation) -> list[SpeakerTurn]:
    _SPEAKER_MAP.clear()
    turns = []
    for segment, _track, label in annotation.itertracks(yield_label=True):
        turns.append(
            SpeakerTurn(
                start=float(segment.start),
                end=float(segment.end),
                speaker=_label_to_name(label),
            )
        )
    return turns


def _load_pipeline():
    """Carga el pipeline de pyannote.

    pyannote 3.x guarda checkpoints con objetos pickled; torch 2.6 cambió el
    default de torch.load a weights_only=True, lo que rompe la carga. Forzamos
    weights_only=False (fuente confiable: modelos oficiales pyannote).
    """
    import torch
    from pyannote.audio import Pipeline

    _orig_load = torch.load

    def _patched_load(*args, **kwargs):
        # Forzar weights_only=False: lightning pasa weights_only=True explícito,
        # así que setdefault no basta. Los checkpoints pyannote requieren False.
        kwargs["weights_only"] = False
        return _orig_load(*args, **kwargs)

    torch.load = _patched_load
    try:
        pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1",
            use_auth_token=config.hf_token,
        )
    finally:
        torch.load = _orig_load
    return pipeline


def diarize(audio_path: str, min_speakers=None, max_speakers=None) -> list[SpeakerTurn]:
    """Devuelve lista de SpeakerTurn. Lista vacía si no hay token o falla.

    min_speakers/max_speakers acotan la detección de pyannote (None = sin límite).
    """
    if not config.hf_token:
        return []
    try:
        import torch

        pipeline = _load_pipeline()
        if torch.cuda.is_available():
            pipeline.to(torch.device("cuda"))

        kwargs = {}
        if min_speakers is not None:
            kwargs["min_speakers"] = min_speakers
        if max_speakers is not None:
            kwargs["max_speakers"] = max_speakers
        annotation = pipeline(audio_path, **kwargs)
        return turns_from_annotation(annotation)
    except Exception:
        logger.exception("Diarización falló; se degrada a sin hablantes")
        return []
