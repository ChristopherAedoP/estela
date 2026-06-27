from app.transcribe import segments_from_whisper, _is_degenerate


class FakeWhisperSeg:
    def __init__(self, start, end, text):
        self.start = start
        self.end = end
        self.text = text


def test_segments_from_whisper_maps_fields():
    raw = [FakeWhisperSeg(0.0, 1.2, " hola "), FakeWhisperSeg(1.2, 2.0, "mundo")]
    result = segments_from_whisper(raw)
    assert len(result) == 2
    assert result[0].start == 0.0
    assert result[0].text == "hola"   # trim aplicado
    assert result[1].text == "mundo"


def test_is_degenerate_detects_word_loop():
    assert _is_degenerate("y Árbol, y Árbol, y Árbol, y Árbol, y Árbol, y Árbol, y Árbol")
    assert _is_degenerate("el bing el bing el bing el bing el bing el bing el bing el bing")
    assert _is_degenerate("")


def test_is_degenerate_allows_normal_text():
    assert not _is_degenerate("Hola equipo, hoy revisamos el avance del proyecto.")
    assert not _is_degenerate("No hay necesidad de pelear por estrellas, ya se la ganaron.")
    assert not _is_degenerate("sí")  # frase corta legítima


def test_segments_filters_degenerate():
    raw = [
        FakeWhisperSeg(0.0, 1.0, "Hola, comencemos la reunión."),
        FakeWhisperSeg(1.0, 5.0, "el bing el bing el bing el bing el bing el bing el bing"),
        FakeWhisperSeg(5.0, 6.0, "Perfecto, sigamos."),
    ]
    result = segments_from_whisper(raw)
    assert len(result) == 2
    assert result[0].text == "Hola, comencemos la reunión."
    assert result[1].text == "Perfecto, sigamos."
