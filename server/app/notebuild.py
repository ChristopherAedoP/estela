from app.models import TranscriptLine


def seconds_to_hms(seconds: float) -> str:
    total = int(seconds)
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def _transcript_block(lines: list[TranscriptLine]) -> str:
    rows = []
    for ln in lines:
        ts = seconds_to_hms(ln.start)
        spk = f"[{ln.speaker}] " if ln.speaker else ""
        rows.append(f"**{spk}{ts}** — {ln.text}")
    return "\n\n".join(rows)


def build_markdown(
    title: str,
    date: str,
    audio_path: str,
    duration_sec: float,
    speakers: int,
    lines: list[TranscriptLine],
    summary_block: str | None,
) -> str:
    fm = (
        "---\n"
        f"title: {title}\n"
        f"date: {date}\n"
        "tags: [acta, reunion, transcripcion]\n"
        f"audio: {audio_path}\n"
        f"duracion: {seconds_to_hms(duration_sec)}\n"
        f"hablantes: {speakers}\n"
        "---\n\n"
    )
    body = f"# {title}\n\n"
    if summary_block:
        body += summary_block + "\n\n"
    body += "## Transcripción\n\n" + _transcript_block(lines) + "\n"
    return fm + body
