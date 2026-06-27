from app.models import TranscriptLine
from app.notebuild import seconds_to_hms, build_markdown


def test_seconds_to_hms():
    assert seconds_to_hms(0) == "00:00:00"
    assert seconds_to_hms(3661) == "01:01:01"


def test_build_markdown_has_frontmatter_and_transcript():
    lines = [TranscriptLine(start=3.0, end=5.0, text="hola equipo")]
    md = build_markdown(
        title="Acta 2026-06-25 - Prueba",
        date="2026-06-25",
        audio_path="/mnt/actas/audio/x.wav",
        duration_sec=3725,
        speakers=0,
        lines=lines,
        summary_block=None,
    )
    assert md.startswith("---")
    assert "title: Acta 2026-06-25 - Prueba" in md
    assert "duracion: 01:02:05" in md
    assert "## Transcripción" in md
    assert "00:00:03" in md
    assert "hola equipo" in md
    # sin resumen en fase 1
    assert "## Resumen" not in md
