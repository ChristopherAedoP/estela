# Changelog

Todos los cambios notables de Estela. Formato basado en
[Keep a Changelog](https://keepachangelog.com/es/1.1.0/).

## [Unreleased]

### Changed
- Renombrado el proyecto de **Actas** a **Estela** (carpeta, app de bandeja, `Estela.exe`,
  single-instance). El identificador técnico interno (`actas-server`, paquete `actas`,
  paths internos y vars `ACTAS_*`) se mantiene para no romper el
  despliegue existente.
- Documentación profesional: README, CHANGELOG, AGENTS.md/CLAUDE.md y `docs/`
  (arquitectura con diagramas C4 en Mermaid, server, client, troubleshooting, decisions).

## [1.0.0] - 2026-06-27

Primera versión funcional completa: grabación → transcripción → diarización → resumen →
acta en el vault, con app de bandeja y procesamiento en cola.

### Cliente (Windows)
- App de escritorio en **Python/PySide6** (bandeja del sistema), compilada a `.exe` con
  PyInstaller. Reemplaza al cliente original basado en scripts PowerShell (archivado en
  `client/OLD/`).
- **Captura con OBS Studio** vía obs-websocket (sin VB-CABLE/ffmpeg): se elige qué salida
  de audio grabar. Grabación **solo-audio** (FFmpeg output, AAC 128k mono, sin video).
- **Cola de procesamiento en background** (FIFO): al detener una grabación se encola y se
  puede grabar otra al instante. Reintento automático de fallidos. Single-instance.
- Hotkey global `Ctrl+Alt+R`, notificaciones toast, iconos de estado (idle/grabando/procesando).
- Ventana de **Ajustes**: salida de audio, ganancia, servidor, vault, carpeta de actas,
  encendido automático de la VM.
- Carpeta de actas configurable (subcarpeta del vault). Nombres únicos (`_2`, `_3`).
- Borrado automático del `.mka` local tras subir (el audio queda archivado en el NAS).
- **Ganancia de audio configurable** (+20dB por defecto) para compensar la captura baja
  de salidas HDMI/NVIDIA (parlantes de monitor).

### Servidor (VM 120, RTX 3060)
- Servicio **FastAPI** (`actas-server`, systemd, puerto 8770). Endpoint `/transcribe`.
- Pipeline: decodificar a WAV PCM (PyAV) → faster-whisper `large-v3` (es) → pyannote
  `speaker-diarization-3.1` → merge texto+hablantes → Ollama `gemma4:12b-it-qat`.
- **Gestión de VRAM**: descarga el modelo de Ollama antes de cargar Whisper (no caben
  juntos en 12 GB).
- Anti-repetición de Whisper (`condition_on_previous_text=False` + filtro de segmentos
  degenerados) y **fallback sin VAD** cuando el VAD descarta todo el audio.
- Diarización mejorada estilo WhisperX (asignación por suma de solapamiento por hablante);
  `min/max_speakers` configurable.
- Guard anti-alucinación: si no hay transcripción, no se invoca el LLM.
- Resumen con `think:false` (compatible gemma4 y qwen3).
- Audio archivado en almacenamiento del servidor (NFS).
- ~28 tests unitarios (pytest).

### Infraestructura
- Almacenamiento del audio via NFS montado en el servidor (configurable por `ACTAS_AUDIO_DIR`).
- Config de OBS versionada (`client-py/obs-config/`).

[Unreleased]: https://github.com/ChristopherAedoP/estela/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/ChristopherAedoP/estela/releases/tag/v1.0.0
