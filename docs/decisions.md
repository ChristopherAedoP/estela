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

**Decisión:** `gemma4:12b-it-qat` como modelo de resumen por defecto; `qwen3:8b` como
fallback.

**Razón:** mejor prosa en español y mejor inferencia de responsables/tareas. Se usa el
parámetro nativo `think:false` de Ollama (compatible con ambos).

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
