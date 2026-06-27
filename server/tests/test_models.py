from app.models import Segment, TranscriptLine, ActaResult


def test_segment_holds_times_and_text():
    s = Segment(start=1.0, end=2.5, text="hola")
    assert s.start == 1.0
    assert s.end == 2.5
    assert s.text == "hola"


def test_transcript_line_default_speaker():
    line = TranscriptLine(start=0.0, end=1.0, text="hola")
    assert line.speaker is None


def test_acta_result_to_dict():
    r = ActaResult(
        title="Acta test",
        duration="00:01:00",
        speakers=0,
        lines=[TranscriptLine(start=0.0, end=1.0, text="hola")],
        markdown="# x",
    )
    d = r.to_dict()
    assert d["title"] == "Acta test"
    assert d["markdown"] == "# x"
