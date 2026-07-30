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
| `ACTAS_WHISPER_DEVICE` | `auto` | `auto`, `cuda` o `cpu` |
| `ACTAS_WHISPER_COMPUTE` | `auto` | `float16` en GPU, `int8` en CPU |
| `ACTAS_LANGUAGE` | `es` | Idioma |
| `ACTAS_AUDIO_DIR` | directorio de datos del usuario | Carpeta donde archivar el audio |
| `ACTAS_TMP_DIR` | temporal del sistema | Temporales del pipeline |
| `ACTAS_MAX_SPEAKERS` | (vacío) | Acotar nº de hablantes |
| `ACTAS_MIN_SPEAKERS` | (vacío) | Mínimo de hablantes |
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
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8770
```

Las rutas por defecto (`ACTAS_AUDIO_DIR`, `ACTAS_TMP_DIR`) y el límite de hilos de las
librerías de álgebra se resuelven solos según la plataforma, así que no hace falta
configurar nada más para arrancar.

El cliente puede arrancar este servidor por su cuenta si lo configuras como respaldo
(`auto_start_local`); en ese caso hereda el entorno del propio cliente.

## Docker

Es el camino recomendado para instalarlo en una máquina nueva: evita el entorno virtual,
las librerías de CUDA y la versión de Python.

```bash
docker compose up                 # servidor + Ollama
docker compose up actas-server    # solo el servidor
```

La segunda forma es la que hay que usar cuando **la máquina ya ejecuta Ollama** para otra
cosa: levantar un segundo Ollama haría que ambos compitieran por la misma VRAM. En ese caso
apunta `ACTAS_OLLAMA_URL` al que ya existe (`http://host.docker.internal:11434` en Docker
Desktop, o la IP del host en Linux).

Ojo con eso: **Ollama escucha solo en `127.0.0.1` por defecto**, así que desde el
contenedor la conexión se rechaza aunque el servicio esté corriendo. Hay que arrancarlo con
`OLLAMA_HOST=0.0.0.0` para que acepte conexiones del contenedor. Si no lo haces, el
servidor transcribe igual y las actas salen con `resumen: pendiente`.

### Comprueba la GPU antes de confiar en ella

`ACTAS_WHISPER_DEVICE=auto` cae a CPU **sin fallar** si el contenedor no ve la GPU, así que
un servidor lento puede parecer que funciona. Verifícalo explícitamente:

```bash
curl "http://localhost:8770/health?deep=1"
```

`checks.pipeline.device` debe decir `cuda`. Si dice `cpu` teniendo GPU, ver
[troubleshooting.md](troubleshooting.md#el-contenedor-no-ve-la-gpu).

Detalles de la imagen:

- Base `python:3.12-slim`; las librerías de CUDA se instalan por pip en vez de partir de una
  imagen base de CUDA. Pesa menos y evita casar la versión de CUDA con la del host, que
  aporta el driver mediante el NVIDIA Container Toolkit.
- Sin el toolkit el contenedor no ve la GPU y cae a CPU. Quita los bloques `deploy:` del
  compose si no lo tienes.
- Volúmenes: `/data/audio` para el audio archivado y `/data/models` para los modelos
  descargados, de modo que sobrevivan a recrear el contenedor.
- El `HEALTHCHECK` usa el `/health` barato. El profundo importa los modelos y tardaría
  demasiado para una comprobación periódica.

## Despliegue (servidor remoto)

```powershell
$env:ESTELA_DEPLOY_HOST = "usuario@host"
pwsh -File deploy.ps1
ssh <user@host> "sudo systemctl restart actas-server"
```

`deploy.ps1` **solo sincroniza código** sobre un servidor ya provisionado: no crea el venv,
ni el usuario del servicio, ni instala el unit, ni escribe `/etc/actas-server.env` (lo
excluye a propósito porque contiene el token de Hugging Face).

El servicio arranca mediante `actas-server-start.sh`, que resuelve `LD_LIBRARY_PATH`
preguntándole al intérprete del venv dónde están las librerías de NVIDIA. Así la versión de
Python no queda cableada en el unit, que era la causa de que un venv con otra versión
produjera `libcublas.so.12 not found`.

El unit trae `User=actas`: créalo o ajústalo al propietario del venv, que además debe poder
escribir en `ACTAS_AUDIO_DIR`. Uvicorn escucha en `0.0.0.0:8770` para que el cliente lo
alcance desde otra máquina.

## API

| Endpoint | Método | Entrada | Respuesta |
|---|---|---|---|
| `/health` | GET | — | `{"status": "ok"}` |
| `/health?deep=1` | GET | — | `{"status": "ok"\|"degraded", "checks": {...}}` |
| `/transcribe` | POST | `multipart/form-data`: `audio` (archivo), `title` (texto) | `{filename, markdown, audio_path, duration_sec}` |

`/transcribe` rechaza con 400 los audios de menos de 1 KB.

`/health` sin parámetros **no ejercita el pipeline**: solo confirma que el proceso HTTP
responde. `torch`, faster-whisper y pyannote se importan de forma perezosa dentro de la
petición, así que un servidor que devuelve `ok` puede fallar igualmente al transcribir. Es
barato a propósito, porque el cliente lo consulta para elegir servidor.

`/health?deep=1` sí lo ejercita: importa las dependencias pesadas, informa del dispositivo
resuelto y comprueba que Ollama responde y tiene el modelo configurado. Devuelve
`degraded` si algo falla. Es la comprobación fiable antes de dar un servidor por bueno:

```json
{"status":"ok","checks":{
  "pipeline":{"torch":true,"faster_whisper":true,"device":"cuda","compute":"float16"},
  "ollama":{"url":"http://127.0.0.1:11434","model":"gemma4:12b-it-qat",
            "reachable":true,"model_present":true}}}
```

La única dependencia pesada que se importa al arrancar es PyAV (`audio.py`); si esa falta,
el proceso no levanta y `/health` no responde en absoluto.

### Nombres de archivo

El título lo escribe el usuario y acaba siendo un nombre de archivo. El servidor lo sanea
en dos formas distintas (`app/naming.py`): `slugify` para el audio archivado, y
`safe_note_name` para el `filename` que devuelve al cliente, que conserva acentos y
mayúsculas por ser el nombre visible en el vault. Ese saneado es también lo que impide que
un título con `..` o `/` haga que el cliente escriba fuera de su carpeta de actas.

## Tests

```bash
# En un despliegue remoto
cd /opt/actas-server && .venv/bin/python -m pytest tests/ -q
```

```powershell
# En local
cd server; .\.venv\Scripts\python -m pytest tests\ -q
```
