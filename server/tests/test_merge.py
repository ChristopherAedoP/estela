from app.models import Segment, SpeakerTurn
from app.merge import assign_speakers


def test_assign_speakers_by_overlap():
    segments = [Segment(0.0, 1.5, "hola"), Segment(2.1, 3.0, "adios")]
    turns = [
        SpeakerTurn(0.0, 2.0, "Hablante 1"),
        SpeakerTurn(2.0, 4.0, "Hablante 2"),
    ]
    lines = assign_speakers(segments, turns)
    assert lines[0].speaker == "Hablante 1"
    assert lines[1].speaker == "Hablante 2"


def test_assign_speakers_empty_turns_returns_none_speaker():
    segments = [Segment(0.0, 1.0, "hola")]
    lines = assign_speakers(segments, [])
    assert lines[0].speaker is None


def test_assign_speakers_sums_overlap_per_speaker():
    # Un segmento [0,10] solapa con: H1 dos tramos (3+3=6s) y H2 un tramo (4s).
    # Aunque el tramo individual de H2 (4s) es mayor que cada tramo de H1 (3s),
    # H1 gana por SUMA total (6 > 4). Esto es la mejora estilo WhisperX.
    segments = [Segment(0.0, 10.0, "frase larga")]
    turns = [
        SpeakerTurn(0.0, 3.0, "Hablante 1"),
        SpeakerTurn(3.0, 7.0, "Hablante 2"),
        SpeakerTurn(7.0, 10.0, "Hablante 1"),
    ]
    lines = assign_speakers(segments, turns)
    assert lines[0].speaker == "Hablante 1"


def test_assign_speakers_no_overlap_returns_none():
    # Segmento sin solape con ningun turno -> sin hablante (fill_nearest desactivado)
    segments = [Segment(10.0, 11.0, "tarde")]
    turns = [SpeakerTurn(0.0, 5.0, "Hablante 1")]
    lines = assign_speakers(segments, turns)
    assert lines[0].speaker is None
