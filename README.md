# Estela

> Graba lo que se dice, déjalo grabado en piedra.

**Estela** es una herramienta personal de **grabación y transcripción de reuniones con
IA 100% local**. Graba el audio que suena en tu PC (reuniones, llamadas, videos), lo
procesa en una máquina con GPU y genera una **acta en markdown** con transcripción en
español, identificación de hablantes, resumen y tareas — guardada automáticamente en tu
vault de Obsidian.

Sin nube. Sin enviar tu audio a terceros. Todo corre en tu propia infraestructura.

## Qué hace

1. **Grabas** con un atajo global (`Ctrl+Alt+R`) — la app vive en la bandeja del sistema.
2. **Captura** el audio de la salida que elijas (vía OBS, sin cables virtuales).
3. **Transcribe** en español (faster-whisper large-v3).
4. **Identifica hablantes** (pyannote) → `[Hablante 1]`, `[Hablante 2]`…
5. **Resume** con un LLM local (gemma4:12b) → resumen, puntos clave, decisiones y tareas.
6. **Guarda** la nota en tu vault Obsidian y archiva el audio en el servidor.

Todo en **background**: grabas una reunión, se encola, y puedes grabar otra al instante.

## Arquitectura (resumen)

```mermaid
flowchart LR
    U([Usuario]) -->|Ctrl+Alt+R| APP[App bandeja<br/>Estela.exe]
    APP -->|WebSocket| OBS[OBS Studio<br/>graba .mka]
    APP -->|HTTP cola| SRV[Servidor FastAPI<br/>maquina con GPU]
    SRV --> W[faster-whisper]
    SRV --> P[pyannote]
    SRV --> L[Ollama gemma4]
    APP -->|escribe| V[(Vault Obsidian)]
    SRV -->|archiva| N[(Almacenamiento NFS)]
```

Detalle completo y diagramas C4 en [`docs/architecture.md`](docs/architecture.md).

## Componentes

| Parte | Tecnología | Ubicación |
|-------|-----------|-----------|
| **Cliente** | Python 3 + PySide6 (app de bandeja) | [`client-py/`](client-py/) → `Estela.exe` |
| **Servidor** | FastAPI + faster-whisper + pyannote + Ollama | [`server/`](server/) — en el mismo PC o en una máquina con GPU |
| **Despliegue** | `deploy.ps1` (scp a un servidor remoto) | raíz |

> Nota: el identificador técnico interno del servicio sigue siendo `actas`
> (`actas-server`, paquete `actas`, variables `ACTAS_*`). "Estela" es el nombre del
> producto. Ver [`docs/decisions.md`](docs/decisions.md).

## Requisitos

- **GPU NVIDIA con CUDA 12.x.** El servidor viene configurado para `cuda`; en CPU funciona
  pero la transcripción se vuelve muy lenta.
- **Python 3.12**, [Ollama](https://ollama.com/download) y, en la máquina donde grabes,
  [OBS Studio](https://obsproject.com/).
- Unos 15 GB de disco para los modelos.

Puedes correrlo **todo en un PC** o separar el cliente del servidor en dos máquinas.

## Quickstart

**Servidor con Docker** (lo más corto; requiere NVIDIA Container Toolkit):

```bash
docker compose up                 # servidor + Ollama
docker compose exec ollama ollama pull gemma4:12b-it-qat
```

**Servidor sin Docker:**

```powershell
cd server
python -m venv .venv
.\.venv\Scripts\pip install torch==2.6.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cu124
.\.venv\Scripts\pip install ".[gpu]"
ollama pull gemma4:12b-it-qat
```

**Cliente (Windows):**

```powershell
cd client-py
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt -r requirements-dev.txt
pwsh -File build.ps1              # genera dist\Estela.exe
```

Ejecuta `Estela.exe`, abre **Ajustes** → apunta al servidor, elige el vault, la salida de
audio y la ganancia, y usa **Ctrl+Alt+R** para grabar.

Este resumen omite pasos que importan (OBS, token de Hugging Face para los hablantes, cómo
exportar el `.env`, cómo verificar que la GPU se ve). Para una puesta en marcha completa
sigue **[`docs/getting-started.md`](docs/getting-started.md)**.

## Documentación

- [`docs/getting-started.md`](docs/getting-started.md) — **Empieza aquí.** Puesta en marcha desde cero.
- [`docs/architecture.md`](docs/architecture.md) — Diagramas C4 + flujo.
- [`docs/configuration.md`](docs/configuration.md) — Variables del servidor, config del cliente, secretos.
- [`docs/server.md`](docs/server.md) — Pipeline, modelos, VRAM, deploy, tests.
- [`docs/client.md`](docs/client.md) — App de bandeja, OBS, ganancia, cola.
- [`docs/troubleshooting.md`](docs/troubleshooting.md) — Problemas resueltos y sus fixes.
- [`docs/decisions.md`](docs/decisions.md) — Decisiones técnicas (ADRs).
- [`CHANGELOG.md`](CHANGELOG.md) — Historial de versiones.

## Stack

Python · PySide6 · OBS Studio (obs-websocket) · FastAPI · faster-whisper (large-v3) ·
pyannote.audio · Ollama (gemma4:12b) · CUDA 12.x · Obsidian

## Estado

**Funcional.** En uso. Proyecto personal de homelab.

## Licencia

[MIT](LICENSE). Se distribuye tal cual, sin garantía.

El audio y las actas que genera Estela **no salen de tu infraestructura**, pero eso depende
de cómo lo despliegues. Antes de compartir tu instalación o el repositorio, revisa qué
archivos contienen secretos en
[`docs/configuration.md`](docs/configuration.md#antes-de-compartir-el-repositorio).

Dos dependencias tienen licencia propia que debes aceptar por tu cuenta:
`pyannote/speaker-diarization-3.1` (requiere aceptar sus condiciones en Hugging Face) y el
modelo de Ollama que elijas para el resumen.
