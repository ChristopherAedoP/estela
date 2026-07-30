# Troubleshooting — Estela

Problemas encontrados durante el desarrollo y sus soluciones. Útil como referencia.

## Servidor (transcripción / GPU)

| Síntoma | Causa | Solución |
|---------|-------|----------|
| `libcublas.so.12 not found` al cargar Whisper | Faltan libs CUDA de runtime | Instalar `nvidia-cublas-cu12` + `nvidia-cudnn-cu12` y exportar `LD_LIBRARY_PATH` en el unit systemd |
| `CUDA out of memory` al cargar Whisper | El LLM y Whisper no caben juntos en ~12GB VRAM | `vram.py`: descargar el modelo de Ollama (`keep_alive=0` / `ollama stop`) antes de cargar Whisper |
| pyannote: `Format not recognised` | El audio llega comprimido (AAC/MKA) y pyannote usa soundfile (no lee AAC) | `audio.py`: decodificar a WAV PCM 16kHz mono con PyAV antes de diarizar |
| `torch.load weights_only` rompe checkpoints pyannote | torch 2.6 cambió el default a `weights_only=True` | Forzar `weights_only=False` al cargar el pipeline (fuente confiable) |
| Whisper repite "palabra palabra palabra…" (loop) | Alucinación de repetición de Whisper | `condition_on_previous_text=False` + parámetros anti-repetición + filtro de segmentos degenerados |
| Transcripción **vacía** con audio claro | El VAD (detección de voz) descarta todo (voces con música/efectos de fondo) | **Fallback**: si el VAD devuelve 0 segmentos, reintentar sin VAD |
| El LLM "inventa" un acta sin audio | Se llamaba al LLM con transcripción vacía | Guard: si no hay texto transcrito, no invocar el LLM; marcar `transcripcion: vacia` |
| Diarización detecta hablantes de más | pyannote sobreestima con ruido | Asignación por suma de solapamiento + `ACTAS_MAX_SPEAKERS` configurable |

## El servidor arranca pero /transcribe devuelve 500

Síntoma típico: `/health` responde `{"status":"ok"}`, el cliente elige ese servidor como
bueno, y cada trabajo falla con
`Server error '500 Internal Server Error' for url '.../transcribe'`. La cola entra en un
bucle de reintentos y las grabaciones se acumulan sin procesar.

**Por qué el health check engaña.** `/health` solo confirma que el proceso HTTP está vivo.
Los modelos pesados (`torch`, faster-whisper, pyannote) se importan de forma perezosa
**dentro** de la petición de transcripción. Si uno de esos imports falla, el servidor
levanta igual y sigue anunciándose como sano.

**Causa más frecuente: OpenBLAS.** Al importar `torch`, OpenBLAS reserva buffers por cada
hilo. En equipos con muchos núcleos, o con la memoria comprometida por otras cargas, esa
reserva falla y aborta el proceso:

```
OpenBLAS error: Memory allocation still failed after 10 retries, giving up.
```

Engaña porque **no es falta de RAM libre**: puede pasar con decenas de GB disponibles, ya
que lo que se agota es la reserva por hilo, no la memoria física.

Diagnóstico — ejecuta el import a mano con el intérprete del venv del servidor:

```powershell
.\.venv\Scripts\python -c "import torch, faster_whisper; print(torch.cuda.is_available())"
```

Si imprime `True`, el problema es otro. Si aborta con el error de OpenBLAS, limita los
hilos:

```powershell
$env:OPENBLAS_NUM_THREADS = "8"
```

Y vuelve a probar. Valores de 8 o menos resuelven el fallo. No se ha medido el impacto en
rendimiento, pero se espera que sea menor, porque el trabajo pesado de Estela ocurre en la
GPU y en Ollama, no en BLAS.

Para que sea permanente y lo hereden los procesos lanzados por el cliente:

```powershell
[Environment]::SetEnvironmentVariable('OPENBLAS_NUM_THREADS','8','User')
```

Después hay que **reiniciar el cliente**, porque el servidor local se lanza como proceso
hijo suyo y hereda su entorno. Ojo: `server/.env` no sirve para esto, ya que el cliente
solo propaga las variables con prefijo `ACTAS_`.

**Otras causas del mismo 500**, si el import de `torch` funciona:

| Causa | Cómo se reconoce |
|---|---|
| Faltan las librerías CUDA de runtime | Error mencionando `libcublas` o `cudnn` |
| Ollama no responde y el audio sí tiene voz | `curl http://127.0.0.1:11434/api/tags` no contesta |

### Lo que NO produce un 500

Que el modelo de `ACTAS_OLLAMA_MODEL` no esté descargado **no** rompe la petición: el fallo
del resumen está capturado, así que el acta se devuelve con la transcripción y el
frontmatter marcado `resumen: pendiente`. Si ves ese marcador, revisa `ollama list` y que
el nombre coincida exactamente. Lo mismo ocurre con la diarización sin `ACTAS_HF_TOKEN`:
degrada a "sin hablantes", no falla.

### Nota sobre los procesos del servidor

En Windows puedes ver **dos** procesos de Python para un solo servidor. Ocurre cuando el
`python.exe` del `.venv` es un redirector que lanza el intérprete base con el entorno del
venv (típico si el Python base viene de la Microsoft Store); con un venv de un Python de
python.org normalmente hay un único proceso. Si te pasa, son padre e hijo: que la línea de
comandos muestre la ruta del Python del sistema **no** significa que el servidor esté
corriendo fuera del venv.

## Cliente (captura / app)

| Síntoma | Causa | Solución |
|---------|-------|----------|
| Subir archivo grande: `Too much data for declared Content-Length` | Pasar un file handle a httpx con archivos grandes | Leer los bytes completos antes de subir |
| OBS genera `.mka` de 0 bytes | Se subía antes de que OBS terminara de escribir | Esperar a que el tamaño del archivo sea estable y > 0 |
| Reintentos en bucle de un archivo corrupto | No se distinguía fallo permanente de transitorio | `PermanentError` (vacío/corrupto) se descarta; los transitorios se reintentan |
| La app se cerraba al emitir señales entre hilos | Señal Qt pasando un objeto Python custom entre threads | Señales con tipos simples (ints) + worker blindado |
| La app se cerraba al guardar Ajustes | Crash nativo de Qt no capturado | `sys.excepthook` + `qInstallMessageHandler` al log + referencias fuertes a ventanas |
| Detección de salidas solo muestra "Por defecto" | OBS tarda en enumerar el audio tras arrancar | Reintentos + verificar que la fuente existe |
| El audio del video se graba **casi mudo** | Las salidas HDMI/NVIDIA (parlantes de monitor) se capturan ~10x más bajo via WASAPI loopback | Filtro de **ganancia +20dB** configurable en Ajustes |
| Grabó pero la transcripción no toma el audio | La escena de OBS tenía una fuente de **video** (Captura de ventana) que metía stream de video al `.mka` | La escena debe tener SOLO la fuente de audio `Audio Escritorio (Actas)` |

## Diagnóstico rápido

1. **¿El audio se capturó?** Revisa el `.mka` antes de que se borre, o el log del cliente.
2. **¿El servidor responde?** `curl http://<host>:8770/health`.
3. **¿Qué dice el log?**
   - Cliente: `%APPDATA%\Actas\actas.log` en Windows
   - Servidor: `journalctl -u actas-server`
4. **¿Transcripción vacía?** Verifica el nivel de audio (ganancia) y que la salida grabada
   sea por donde realmente suena.
