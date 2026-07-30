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
5. **Archivar** el audio original (`archive.py`) y borrar los temporales.
6. **Fusionar** texto + hablantes (`merge.py`, suma de solapamiento).
7. **Resumir** (`summarize.py`, Ollama) — resumen, puntos, decisiones, tareas.
   - Guard: si no hay transcripción, no se invoca el LLM.
8. **Construir** el markdown (`notebuild.py`).

Devuelve `{ filename, markdown, audio_path, duration_sec }`.

## Modelos

| Etapa | Modelo |
|-------|--------|
| Transcripción | `faster-whisper large-v3` (float16, CUDA) |
| Diarización | `pyannote/speaker-diarization-3.1` (requiere token HF + licencias) |
| Resumen | Ollama, modelo de `ACTAS_OLLAMA_MODEL` (por defecto `gemma4:12b-it-qat`) |

El modelo del resumen debe estar descargado en Ollama (`ollama pull`). No hay modelo de
respaldo: si el configurado no está disponible, el acta se genera igual con la
transcripción, marcada con `resumen: pendiente`.

## Configuración (variables de entorno)

Ver `server/.env.example`. El archivo real no se versiona y su ubicación depende del modo:
`server/.env` al ejecutarlo en local, `/etc/actas-server.env` bajo systemd (lo declara
`EnvironmentFile` en el unit).

| Variable | Default | Descripción |
|----------|---------|-------------|
| `ACTAS_HF_TOKEN` | (vacío) | Token Hugging Face para pyannote (requerido para diarizar) |
| `ACTAS_OLLAMA_MODEL` | `gemma4:12b-it-qat` | LLM del resumen |
| `ACTAS_OLLAMA_URL` | `http://127.0.0.1:11434` | URL de Ollama |
| `ACTAS_WHISPER_MODEL` | `large-v3` | Modelo Whisper |
| `ACTAS_WHISPER_COMPUTE` | `float16` | Precisión |
| `ACTAS_LANGUAGE` | `es` | Idioma |
| `ACTAS_AUDIO_DIR` | `/mnt/actas/audio` | Carpeta donde archivar el audio |
| `ACTAS_WHISPER_DEVICE` | `cuda` | `cuda` o `cpu` |
| `ACTAS_TMP_DIR` | `/tmp/actas` | Temporales del pipeline |
| `ACTAS_MAX_SPEAKERS` | (vacío) | Acotar nº de hablantes |
| `ACTAS_MIN_SPEAKERS` | (vacío) | Mínimo de hablantes |

Referencia completa, incluida la configuración del cliente y qué archivos llevan secretos:
[configuration.md](configuration.md).

## Gestión de VRAM (crítico)

En GPUs de ~12GB, el LLM y Whisper + pyannote no caben juntos. El pipeline descarga el
modelo de Ollama antes de cargar Whisper y libera la caché de torch entre etapas. Sin esto
→ `CUDA out of memory`. Las cifras de referencia (LLM ~9GB, Whisper ~3GB) provienen de las
pruebas del autor en una RTX 3060 y varían según el modelo y la cuantización.

## Requisitos CUDA

- faster-whisper (CTranslate2) necesita `nvidia-cublas-cu12` + `nvidia-cudnn-cu12`; exportar
  `LD_LIBRARY_PATH` en el unit systemd.
- torch/torchaudio compilados para la versión de CUDA del driver instalado.

## Ejecutar en local (Windows)

Útil si corres cliente y servidor en el mismo PC. El código **no carga el `.env` por sí
solo** (en producción lo inyecta systemd), así que hay que exportar las variables antes:

```powershell
cd server
Get-Content .env | Where-Object { $_ -match '^\s*ACTAS_' } | ForEach-Object {
    $k,$v = $_ -split '=',2
    [System.Environment]::SetEnvironmentVariable($k.Trim(), $v.Trim(), 'Process')
}
$env:OPENBLAS_NUM_THREADS = "8"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8770
```

Dos avisos para este modo:

- `ACTAS_AUDIO_DIR` y `ACTAS_TMP_DIR` tienen defaults de Linux (`/mnt/actas/audio`,
  `/tmp/actas`). Hay que cambiarlos a rutas de Windows.
- `OPENBLAS_NUM_THREADS` evita que OpenBLAS aborte el proceso al importar `torch` en
  equipos con muchos núcleos. Ver
  [troubleshooting.md](troubleshooting.md#el-servidor-arranca-pero-transcribe-devuelve-500).

El cliente puede arrancar este servidor por su cuenta si lo configuras como respaldo
(`auto_start_local`); en ese caso hereda el entorno del propio cliente.

## Despliegue (servidor remoto)

```powershell
$env:ESTELA_DEPLOY_HOST = "usuario@host"
pwsh -File deploy.ps1
ssh <user@host> "sudo systemctl restart actas-server"
```

El servicio `actas-server.service` corre con uvicorn en el puerto 8770. Para que el cliente
lo alcance desde otra máquina, uvicorn debe escuchar en `0.0.0.0`, no en `127.0.0.1`.

## API

| Endpoint | Método | Entrada | Respuesta |
|---|---|---|---|
| `/health` | GET | — | `{"status": "ok"}` |
| `/transcribe` | POST | `multipart/form-data`: `audio` (archivo), `title` (texto) | `{filename, markdown, audio_path, duration_sec}` |

`/transcribe` rechaza con 400 los audios de menos de 1 KB.

`/health` **no ejercita el pipeline**: solo confirma que el proceso HTTP responde. `torch`,
faster-whisper y pyannote se importan de forma perezosa dentro de la petición, así que un
servidor que devuelve `ok` puede fallar igualmente al transcribir. La única dependencia
pesada que se importa al arrancar es PyAV (`audio.py`); si esa falta, el proceso no levanta
y `/health` no responde.

## Tests

```bash
# En un despliegue remoto
cd /opt/actas-server && .venv/bin/python -m pytest tests/ -q
```

```powershell
# En local
cd server; .\.venv\Scripts\python -m pytest tests\ -q
```
