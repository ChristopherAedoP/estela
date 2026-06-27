import os
import datetime as dt
import logging
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from app.config import config
from app.transcribe import transcribe
from app.archive import archive_audio
from app.audio import decode_to_wav
from app.notebuild import build_markdown
from app.summarize import summarize
from app.diarize import diarize
from app.merge import assign_speakers
from app.vram import unload_ollama_model, free_torch_cache
from app.models import TranscriptLine

logger = logging.getLogger("actas.main")

app = FastAPI(title="actas-server")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/transcribe")
async def transcribe_endpoint(
    audio: UploadFile = File(...),
    title: str = Form("Reunión"),
):
    os.makedirs(config.tmp_dir, exist_ok=True)
    date = dt.date.today().isoformat()
    safe_title = title.strip() or "Reunión"
    note_title = f"Acta {date} - {safe_title}"

    raw = await audio.read()
    if len(raw) < 1024:
        raise HTTPException(status_code=400, detail="Audio vacío o demasiado corto")

    # Guardar el upload con su contenido real (puede ser AAC/MKA, no WAV)
    src_path = os.path.join(config.tmp_dir, f"{date}_{safe_title}.src")
    with open(src_path, "wb") as f:
        f.write(raw)

    # Decodificar a WAV PCM 16kHz mono real: pyannote usa soundfile (no lee AAC)
    # y whisper también funciona bien con WAV PCM.
    wav_path = os.path.join(config.tmp_dir, f"{date}_{safe_title}.proc.wav")
    try:
        decode_to_wav(src_path, wav_path)
        proc_path = wav_path
    except Exception:
        logger.exception("decode_to_wav falló; se usa el archivo original")
        proc_path = src_path

    # VRAM: liberar qwen3 de Ollama antes de cargar Whisper (no caben juntos en 12GB)
    unload_ollama_model()

    segments, duration = transcribe(proc_path)
    free_torch_cache()

    # Diarización (quién habla); lista vacía si no hay token o falla -> sin hablantes
    turns = diarize(
        proc_path,
        min_speakers=config.min_speakers,
        max_speakers=config.max_speakers,
    )
    free_torch_cache()

    # Archivar el audio original comprimido (opción A: liviano)
    audio_path = archive_audio(src_path, safe_title, date)

    # Limpiar temporales (el original ya está archivado en el NAS)
    for p in (wav_path, src_path):
        try:
            if os.path.exists(p):
                os.remove(p)
        except Exception:
            pass

    lines = assign_speakers(segments, turns)
    speaker_names = {ln.speaker for ln in lines if ln.speaker}
    speakers = len(speaker_names)

    transcript_text = "\n".join(s.text for s in segments).strip()

    # Si no hay transcripción (audio en silencio / sin habla), NO llamar al LLM:
    # qwen3 alucinaría un acta inventada. Se marca la nota como vacía.
    if not transcript_text:
        markdown = build_markdown(
            title=note_title,
            date=date,
            audio_path=audio_path,
            duration_sec=duration,
            speakers=speakers,
            lines=lines,
            summary_block=None,
        )
        markdown = markdown.replace(
            "tags: [acta, reunion, transcripcion]\n",
            "tags: [acta, reunion, transcripcion]\ntranscripcion: vacia\n",
        )
        return {
            "filename": f"{note_title}.md",
            "markdown": markdown,
            "audio_path": audio_path,
            "duration_sec": duration,
        }

    summary_block, summary_ok = summarize(transcript_text)

    markdown = build_markdown(
        title=note_title,
        date=date,
        audio_path=audio_path,
        duration_sec=duration,
        speakers=speakers,
        lines=lines,
        summary_block=summary_block,
    )
    if not summary_ok:
        markdown = markdown.replace(
            "tags: [acta, reunion, transcripcion]\n",
            "tags: [acta, reunion, transcripcion]\nresumen: pendiente\n",
        )

    return {
        "filename": f"{note_title}.md",
        "markdown": markdown,
        "audio_path": audio_path,
        "duration_sec": duration,
    }
