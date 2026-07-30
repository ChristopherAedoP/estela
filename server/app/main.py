import os
import datetime as dt
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from app.config import config
from app.transcribe import transcribe
from app.archive import archive_audio
from app.naming import safe_note_name, slugify
from app.audio import decode_to_wav
from app.notebuild import build_markdown
from app.summarize import summarize
from app.diarize import diarize
from app.merge import assign_speakers
from app.vram import unload_ollama_model, free_torch_cache
from app.models import TranscriptLine
from app.runtime import ollama_status, pipeline_status, whisper_uses_cuda

logger = logging.getLogger("actas.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Avisa al arrancar si Ollama no esta listo.

    Un Ollama caido, o sin el modelo configurado, no rompe la transcripcion: el
    acta sale con la transcripcion y marcada 'resumen: pendiente'. Como el fallo
    es silencioso (HTTP 200), conviene dejarlo dicho en el log al arrancar.

    A proposito NO se comprueba aqui el pipeline de transcripcion: importar torch
    y los modelos retrasaria el arranque varios segundos. Para eso esta
    /health?deep=1.
    """
    try:
        ready, detail = ollama_status()
        if ready:
            logger.info("Ollama listo: %s", detail)
        else:
            logger.warning(
                "Ollama no esta listo (%s). La transcripcion funcionara, pero las "
                "actas saldran marcadas 'resumen: pendiente'.",
                detail,
            )
    except Exception:
        logger.exception("No se pudo comprobar el estado de Ollama al arrancar")
    yield


app = FastAPI(title="actas-server", lifespan=lifespan)


@app.get("/health")
def health(deep: bool = False):
    """Estado del servidor.

    Sin parametros es una comprobacion barata: confirma que el proceso HTTP
    responde. El cliente la usa para elegir servidor, por lo que debe ser rapida.

    Con deep=1 ejercita las dependencias reales del pipeline. Es la unica forma
    fiable de saber si el servidor puede transcribir: los modelos se importan de
    forma perezosa dentro de la peticion, asi que un servidor con la pila rota
    responde 'ok' a la comprobacion barata y falla despues en /transcribe.
    """
    if not deep:
        return {"status": "ok"}

    checks: dict = {}
    ok = True

    pipeline_ok, pipeline_detail = pipeline_status()
    checks["pipeline"] = pipeline_detail
    if not pipeline_ok:
        ok = False

    ready, detail = ollama_status()
    checks["ollama"] = detail
    if not ready:
        ok = False

    return {"status": "ok" if ok else "degraded", "checks": checks}


@app.post("/transcribe")
async def transcribe_endpoint(
    audio: UploadFile = File(...),
    title: str = Form("Reunión"),
):
    os.makedirs(config.tmp_dir, exist_ok=True)
    date = dt.date.today().isoformat()
    safe_title = title.strip() or "Reunión"
    note_title = f"Acta {date} - {safe_title}"
    # El cliente escribe la nota usando este nombre tal cual, dentro de su carpeta
    # de actas. Sanearlo aqui es lo que impide que un titulo con '..' o '/' le haga
    # escribir fuera, y que un titulo con ':' falle al guardar en Windows.
    note_filename = f"{safe_note_name(note_title)}.md"

    raw = await audio.read()
    if len(raw) < 1024:
        raise HTTPException(status_code=400, detail="Audio vacío o demasiado corto")

    # El titulo lo escribe el usuario y se usa como nombre de archivo: hay que
    # sanearlo. Sin esto, un titulo con ':' o '?' falla en Windows, y uno con '/'
    # o '..' permitiria escribir fuera de tmp_dir.
    slug = slugify(safe_title)

    # Guardar el upload con su contenido real (puede ser AAC/MKA, no WAV)
    src_path = os.path.join(config.tmp_dir, f"{date}_{slug}.src")
    with open(src_path, "wb") as f:
        f.write(raw)

    # Decodificar a WAV PCM 16kHz mono real: pyannote usa soundfile (no lee AAC)
    # y whisper también funciona bien con WAV PCM.
    wav_path = os.path.join(config.tmp_dir, f"{date}_{slug}.proc.wav")
    try:
        decode_to_wav(src_path, wav_path)
        proc_path = wav_path
    except Exception:
        logger.exception("decode_to_wav falló; se usa el archivo original")
        proc_path = src_path

    # VRAM: si Whisper va a usar la GPU, liberar antes el modelo de Ollama, porque
    # en tarjetas de ~12 GB no caben juntos. En CPU no compiten por VRAM y
    # descargarlo solo forzaria una recarga completa del LLM al resumir.
    if whisper_uses_cuda():
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
            "filename": note_filename,
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
        "filename": note_filename,
        "markdown": markdown,
        "audio_path": audio_path,
        "duration_sec": duration,
    }
