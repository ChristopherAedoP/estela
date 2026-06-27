from app.models import Segment, SpeakerTurn, TranscriptLine


def _overlap(a_start, a_end, b_start, b_end) -> float:
    return max(0.0, min(a_end, b_end) - max(a_start, b_start))


def assign_speakers(
    segments: list[Segment], turns: list[SpeakerTurn]
) -> list[TranscriptLine]:
    """Asigna hablante a cada segmento por SUMA de solapamiento por hablante.

    Estilo WhisperX (assign_word_speakers): en vez de elegir el único turno con
    mayor solapamiento, se suma el solapamiento total de cada hablante con el
    segmento y se elige el de mayor suma. Más robusto cuando hay varios turnos
    cortos intercalados. Si no hay solapamiento (>0), el segmento queda sin
    hablante (fill_nearest desactivado).
    """
    lines = []
    for seg in segments:
        speaker = None
        if turns:
            totals: dict[str, float] = {}
            for t in turns:
                ov = _overlap(seg.start, seg.end, t.start, t.end)
                if ov > 0:
                    totals[t.speaker] = totals.get(t.speaker, 0.0) + ov
            if totals:
                speaker = max(totals, key=totals.get)
        lines.append(
            TranscriptLine(start=seg.start, end=seg.end, text=seg.text, speaker=speaker)
        )
    return lines
