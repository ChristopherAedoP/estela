# Arquitectura — Estela

Arquitectura del sistema descrita con el modelo **C4** (Contexto → Contenedores →
Componentes) y un diagrama de secuencia del flujo principal. Diagramas en Mermaid.

## C4 — Nivel 1: Contexto

Visión general: quién usa Estela y con qué sistemas externos interactúa.

```mermaid
C4Context
    title Estela - Diagrama de Contexto

    Person(user, "Usuario", "Graba reuniones, llamadas y videos en su PC")

    System(estela, "Estela", "Graba audio del sistema, transcribe, diariza y resume con IA local")

    System_Ext(obs, "OBS Studio", "Captura el audio de la salida elegida")
    System_Ext(vault, "Vault Obsidian", "Almacena las actas en markdown")
    System_Ext(nas, "Almacenamiento (NFS)", "Archiva el audio original")
    System_Ext(proxmox, "Proxmox VE", "Enciende la VM 120 bajo demanda")

    Rel(user, estela, "Graba (Ctrl+Alt+R), lee actas")
    Rel(estela, obs, "Controla grabacion", "obs-websocket v5")
    Rel(estela, vault, "Escribe la nota .md")
    Rel(estela, nas, "Archiva el audio", "NFS")
    Rel(estela, proxmox, "Enciende la VM", "SSH / qm start")
```

## C4 — Nivel 2: Contenedores

Las piezas ejecutables y dónde corren (PC Windows vs VM 120 con GPU).

```mermaid
C4Container
    title Estela - Diagrama de Contenedores

    Person(user, "Usuario")

    System_Boundary(pc, "PC Windows") {
        Container(app, "App de bandeja", "Python / PySide6", "Tray, hotkey, cola FIFO, ajustes. Estela.exe")
        Container(obs, "OBS Studio", "WASAPI + FFmpeg", "Graba .mka solo-audio de la salida elegida")
    }

    System_Boundary(vm, "Servidor con GPU (RTX, Linux)") {
        Container(server, "actas-server", "FastAPI / Uvicorn", "Pipeline de transcripcion. Puerto 8770")
        Container(whisper, "faster-whisper", "large-v3 / CUDA", "Audio -> texto (es)")
        Container(pyannote, "pyannote.audio", "speaker-diarization-3.1", "Quien habla")
        Container(ollama, "Ollama", "gemma4:12b-it-qat", "Resumen + tareas")
    }

    ContainerDb(vault, "Vault Obsidian", "Markdown", "Carpeta Actas/ del vault")
    ContainerDb(nfs, "Almacenamiento NFS", "Servidor", "Audio .mka archivado")

    Rel(user, app, "Ctrl+Alt+R")
    Rel(app, obs, "start/stop record", "WebSocket :4455")
    Rel(app, server, "POST /transcribe", "HTTP")
    Rel(server, whisper, "transcribe")
    Rel(server, pyannote, "diarize")
    Rel(server, ollama, "summarize", "HTTP :11434")
    Rel(app, vault, "escribe .md")
    Rel(server, nfs, "archiva audio")
```

## C4 — Nivel 3: Componentes (actas-server)

Módulos internos del servidor y el orden del pipeline.

```mermaid
C4Component
    title Estela - Componentes del actas-server

    Container_Boundary(api, "actas-server (FastAPI)") {
        Component(main, "main.py", "Endpoint", "Orquesta /transcribe, guard de audio vacio")
        Component(audio, "audio.py", "PyAV", "Decodifica .mka -> WAV PCM 16k mono")
        Component(transcribe, "transcribe.py", "faster-whisper", "Texto + fallback sin VAD + anti-repeticion")
        Component(diarize, "diarize.py", "pyannote", "Turnos por hablante, min/max speakers")
        Component(merge, "merge.py", "Logica", "Asigna hablante por suma de solapamiento")
        Component(summarize, "summarize.py", "Ollama", "Resumen/Puntos/Decisiones/Tareas")
        Component(vram, "vram.py", "Gestion GPU", "Descarga Ollama antes de Whisper")
        Component(notebuild, "notebuild.py", "Markdown", "Construye el acta")
        Component(archive, "archive.py", "NFS", "Copia el audio original")
    }

    Rel(main, audio, "1. decodifica")
    Rel(main, vram, "2. libera GPU")
    Rel(main, transcribe, "3. transcribe")
    Rel(main, diarize, "4. diariza")
    Rel(main, merge, "5. fusiona")
    Rel(main, summarize, "6. resume")
    Rel(main, notebuild, "7. genera md")
    Rel(main, archive, "8. archiva")
```

## Flujo principal (secuencia)

De pulsar el atajo a tener el acta en el vault. Grabar y procesar están desacoplados:
tras detener, el trabajo se encola y la app queda libre para grabar otra.

```mermaid
sequenceDiagram
    actor U as Usuario
    participant A as App (bandeja)
    participant O as OBS
    participant Q as Cola FIFO
    participant S as actas-server
    participant V as Vault

    U->>A: Ctrl+Alt+R (iniciar)
    A->>O: StartRecord (WebSocket)
    U->>A: Ctrl+Alt+R (detener) + titulo
    A->>O: StopRecord -> ruta .mka
    A->>Q: encola trabajo
    Note over A,U: vuelve a idle - puede grabar otra
    Q->>S: POST /transcribe (.mka)
    S->>S: decode WAV -> whisper -> pyannote -> merge -> gemma4
    S-->>Q: markdown del acta
    Q->>V: escribe Acta ...md
    Q->>Q: borra .mka local
    Q-->>A: toast "Acta lista"
```

## Decisiones clave de arquitectura

- **Cliente/servidor separados**: el PC graba (ligero); la VM con GPU procesa (pesado).
  El servidor solo se enciende bajo demanda (`onboot=0`).
- **Cola en background**: desacopla grabar de procesar; permite grabar varias seguidas.
- **Gestión de VRAM**: en la RTX 3060 (12 GB) el LLM y Whisper no caben juntos; se
  descarga Ollama antes de cargar Whisper.
- **OBS para captura**: evita VB-CABLE/cables virtuales; captura cualquier salida WASAPI.
- **El repo es la fuente de verdad**; la VM y el `.exe` son despliegues.

Ver razones detalladas en [decisions.md](decisions.md).
