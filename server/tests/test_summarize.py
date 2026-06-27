import app.summarize as sm
from app.summarize import build_prompt, parse_summary, summarize


def test_build_prompt_includes_transcript():
    p = build_prompt("**00:00:01** — hola")
    assert "hola" in p
    assert "Resumen" in p


def test_parse_summary_extracts_sections():
    raw = (
        "## Resumen\nReunión sobre X.\n\n"
        "## Puntos clave\n- a\n- b\n\n"
        "## Decisiones\n- d1\n\n"
        "## Tareas\n- [ ] (Ana) hacer algo\n"
    )
    block = parse_summary(raw)
    assert "## Resumen" in block
    assert "Reunión sobre X." in block
    assert "## Tareas" in block


def test_summarize_returns_pending_on_error(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("ollama down")
    monkeypatch.setattr(sm, "_call_ollama", boom)
    block, ok = summarize("transcripción")
    assert ok is False
    assert block is None
