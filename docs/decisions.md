# Decisiones técnicas (ADRs) — Estela

Registro de las decisiones de arquitectura y sus razones.

## 1. Cliente/servidor separados

**Decisión:** el cliente (PC) solo graba y orquesta; el procesamiento pesado (IA) corre en
un servidor con GPU que se enciende bajo demanda.

**Razón:** el PC no necesita GPU potente; la transcripción/diarización/LLM requieren GPU.
Separa responsabilidades y permite apagar el servidor cuando no se usa.

## 2. Captura con OBS en vez de VB-CABLE/ffmpeg

**Decisión:** usar OBS Studio (obs-websocket) para capturar el audio.

**Razón:** el PC de referencia no tiene "Stereo Mix" y la salida es HDMI/Bluetooth.
VB-CABLE obligaba a re-rutear el audio (incómodo). ffmpeg/dshow no captura la salida del
sistema sin un loopback. OBS captura cualquier salida WASAPI directamente y se controla por
WebSocket. Se eligió grabar **solo-audio** (FFmpeg output, `FFVBitrate=0`) para archivos
livianos.

## 3. LLM para el resumen: gemma4:12b (no qwen3)

**Decisión:** `gemma4:12b-it-qat` como modelo de resumen por defecto.

**Razón:** mejor prosa en español y mejor inferencia de responsables/tareas que `qwen3:8b`,
que era el modelo anterior. Se usa el parámetro nativo `think:false` de Ollama (compatible
con ambos).

**Estado de la implementación:** no hay fallback de modelo. `summarize.py` llama únicamente
al modelo de `ACTAS_OLLAMA_MODEL`; si falla, el acta se genera igual con la transcripción y
se marca `resumen: pendiente`. Cambiar de modelo es solo cambiar esa variable.

## 4. NO usar gemma-3n para transcribir (descartado)

**Decisión:** mantener Whisper para la transcripción; no usar gemma-3n (multimodal con audio).

**Razón:** verificado en HuggingFace/Ollama — Ollama **no expone** el audio de gemma-3n
(solo texto via llama.cpp); usarlo requeriría otro runtime (transformers/vLLM), no diariza
(igual necesita pyannote), y su ASR (USM) está orientado a audio corto. Whisper large-v3 es
mejor para reuniones largas en español.

## 5. WhisperX: adoptar su lógica, no instalarlo

**Decisión:** replicar la lógica de asignación de hablantes de WhisperX (suma de
solapamiento por hablante) en `merge.py`, sin instalar WhisperX.

**Razón:** WhisperX moderno exige torch 2.7 / CUDA 12.8; el entorno usa CUDA 12.4. Instalarlo
implicaría actualizar el driver de la GPU del servidor, con riesgo para otros servicios que
comparten esa máquina. Los word-level timestamps (que sí requieren WhisperX completo) quedan
como mejora futura.

## 6. Cola de procesamiento en background

**Decisión:** desacoplar grabar de procesar con una cola FIFO persistente.

**Razón:** procesar una reunión larga tarda minutos; bloquear la app impediría grabar otra.
Con la cola, al detener una grabación se encola y la app queda libre al instante.

## 7. Configuración externalizada (no hardcodeada)

**Decisión:** el código no contiene config de infraestructura ni secretos. Cliente: defaults
neutros + `config.json` del usuario (UI Ajustes). Servidor: variables de entorno (`ACTAS_*`).

**Razón:** principios 12-factor / separación de configuración y código. Permite versionar el
código sin exponer hosts, rutas ni credenciales, y desplegar en distintos entornos.

## 8. "Estela" (producto) vs "actas" (interno)

**Decisión:** el producto se llama Estela; el identificador técnico interno sigue siendo
`actas` (servicio, paquete python, variables).

**Razón:** renombrar todo lo interno (servicio systemd, paquete, paths) rompería despliegues
y configuración existentes sin beneficio funcional. El nombre visible es lo que importa para
el usuario.

## 9. Fallback de servidor: NAS primario, local de respaldo

**Decisión:** el cliente resuelve el servidor a usar en cada trabajo con una cascada
(`infra.resolve_server`): 1) servidor primario (`server_url`) si responde; 2) si
`auto_start_vm`, encender la VM y esperar; 3) servidor local (`local_server_url`) si
responde; 4) si `auto_start_local`, arrancar Ollama + actas-server local y usarlo. El primer
servidor disponible procesa el trabajo (`recorder` guarda la URL efectiva y `_upload` la usa).

**Razón:** el servidor primario (VM con GPU en el NAS) no siempre está encendido. Con la
cascada, la grabación se procesa contra el NAS cuando está disponible y contra el PC local
cuando no, sin intervención ni cambio de configuración. El PC local tiene GPU suficiente
(16 GB VRAM) para el pipeline completo.

**Limitación conocida:** `start_local_server` lanza el uvicorn del server local como proceso
hijo del cliente; si el cliente termina justo tras arrancarlo, el server local también
termina. En uso normal la app de bandeja vive mientras se procesa la cola. Mejora futura:
lanzar el server local desacoplado del proceso padre.
