import app.diarize as dz
from app.diarize import turns_from_annotation, diarize


class FakeAnnotation:
    def itertracks(self, yield_label=True):
        class Seg:
            def __init__(self, s, e):
                self.start = s
                self.end = e

        yield (Seg(0.0, 2.0), "_", "SPEAKER_00")
        yield (Seg(2.0, 4.0), "_", "SPEAKER_01")


def test_turns_from_annotation_maps_speakers():
    turns = turns_from_annotation(FakeAnnotation())
    assert len(turns) == 2
    assert turns[0].speaker == "Hablante 1"
    assert turns[1].speaker == "Hablante 2"
    assert turns[0].start == 0.0


def test_diarize_returns_empty_without_token(monkeypatch):
    monkeypatch.setattr(dz.config, "hf_token", "")
    turns = diarize("cualquier.wav")
    assert turns == []
