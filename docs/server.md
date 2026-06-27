# Servidor (actas-server) — Estela

Servicio FastAPI que ejecuta el pipeline de transcripción en una máquina con GPU.

## Pipeline (`/transcribe`)

Entrada: `multipart/form-data` con `audio` (.mka) y `title`. Pasos:

1. **Guardar** el upload y **decodificar** a WAV PCM 16kHz mono (`audio.py`, PyAV).
2. **Liberar VRAM**: descargar el modelo de Ollama (`vram.py`).
3. **Transcribir** (`transcribe.py`, faster-whisper `large-v3`, español).
   - Anti-repetición (`condition_on_previous_text=False`, etc.).
   - **Fallback sin VAD** si el VAD descarta todo el audio.
4. **Diarizar** (`diarize.py`, pyannote) — turnos por hablante; `min/max_speakers` opcional.
5. **Fusionar** texto + hablantes (`merge.py`, suma de solapamiento).
6. **Resumir** (`summarize.py`, Ollama) — resumen, puntos, decisiones, tareas.
   - Guard: si no hay transcripción, no se invoca el LLM.
7. **Construir** el markdown (`notebuild.py`) y **archivar** el audio (`archive.py`).

Devuelve `{ filename, markdown, audio_path, duration_sec }`.

## Modelos

| Etapa | Modelo |
|-------|--------|
| Transcripción | `faster-whisper large-v3` (float16, CUDA) |
| Diarización | `pyannote/speaker-diarization-3.1` (requiere token HF + licencias) |
| Resumen | Ollama `gemma4:12b-it-qat` (fallback `qwen3:8b`) |

## Configuración (variables de entorno)

Ver `server/.env.example`. Se cargan desde un archivo `.env` en el servidor (fuera de git):

| Variable | Default | Descripción |
|----------|---------|-------------|
| `ACTAS_HF_TOKEN` | (vacío) | Token Hugging Face para pyannote (requerido para diarizar) |
| `ACTAS_OLLAMA_MODEL` | `gemma4:12b-it-qat` | LLM del resumen |
| `ACTAS_OLLAMA_URL` | `http://127.0.0.1:11434` | URL de Ollama |
| `ACTAS_WHISPER_MODEL` | `large-v3` | Modelo Whisper |
| `ACTAS_WHISPER_COMPUTE` | `float16` | Precisión |
| `ACTAS_LANGUAGE` | `es` | Idioma |
| `ACTAS_AUDIO_DIR` | `/mnt/actas/audio` | Carpeta donde archivar el audio |
| `ACTAS_MAX_SPEAKERS` | (vacío) | Acotar nº de hablantes |
| `ACTAS_MIN_SPEAKERS` | (vacío) | Mínimo de hablantes |

## Gestión de VRAM (crítico)

En GPUs de ~12GB, el LLM (~9GB) y Whisper (~3GB) + pyannote no caben juntos. El pipeline
descarga el modelo de Ollama antes de cargar Whisper y libera la caché de torch entre
etapas. Sin esto → `CUDA out of memory`.

## Requisitos CUDA

- faster-whisper (CTranslate2) necesita `nvidia-cublas-cu12` + `nvidia-cudnn-cu12`; exportar
  `LD_LIBRARY_PATH` en el unit systemd.
- torch/torchaudio compilados para la versión de CUDA del driver instalado.

## Despliegue

```powershell
$env:ESTELA_DEPLOY_HOST = "usuario@host"
pwsh -File deploy.ps1
ssh <user@host> "sudo systemctl restart actas-server"
```

El servicio `actas-server.service` corre con uvicorn en el puerto 8770.

## Tests

```bash
cd /opt/actas-server && .venv/bin/python -m pytest tests/ -q
```
