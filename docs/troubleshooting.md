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
   - Cliente: `<dir-datos>/Estela/actas.log`
   - Servidor: `journalctl -u actas-server`
4. **¿Transcripción vacía?** Verifica el nivel de audio (ganancia) y que la salida grabada
   sea por donde realmente suena.
