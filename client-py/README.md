# Estela — Cliente de escritorio (Python / PySide6)

App de **bandeja del sistema** para grabar una salida de audio del PC, enviarla al servidor
de transcripción y obtener una **acta en español con identificación de hablantes, resumen y
tareas**, guardada como nota en un vault Obsidian.

Reemplaza al cliente anterior basado en scripts PowerShell (`../client/OLD/`). La grabación
usa **OBS Studio** vía obs-websocket (sin cables virtuales): eliges qué salida capturar.

Documentación completa del cliente en [`../docs/client.md`](../docs/client.md).

## Características

- Icono en la **bandeja**: gris (inactivo), rojo (grabando), ámbar (procesando).
- **Clic** en el icono o **Ctrl+Alt+R** para iniciar/detener.
- **Diálogo de título** de la reunión antes de procesar.
- **Ventana de Ajustes**: salida de audio, ganancia, servidor, vault, carpeta de actas,
  encendido automático del servidor.
- **Cola en background**: grabas una y puedes grabar otra al instante; reintento de fallidos.
- **Notificaciones** nativas. Sin consolas. Procesamiento en hilo aparte.

## Configuración

El código tiene defaults neutros; la config real se introduce en **Ajustes** y se guarda en
`config.json` del directorio de datos del usuario (fuera de git). Ver
[`config.example.json`](config.example.json).

## Desarrollo

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\python -m actas        # ejecuta la app
```

## Compilar a .exe (Windows)

```powershell
.\.venv\Scripts\pip install pyinstaller
pwsh -File build.ps1                    # genera dist\Estela.exe (autocontenido, sin consola)
```

## Arranque automático con Windows

Crear un acceso directo a `dist\Estela.exe` en la carpeta `shell:startup`.

## Requisitos

- **OBS Studio** (`winget install OBSProject.OBSStudio`). Config de ejemplo en `obs-config/`.
- El **servidor** de transcripción corriendo (ver `../server/` y `../docs/server.md`).
- SSH por clave al host del servidor si se usa el encendido automático.

## Módulos

| Módulo | Responsabilidad |
|--------|-----------------|
| `config.py` | Config persistente (defaults neutros + JSON del usuario) |
| `obs_client.py` | Cliente obs-websocket v5 (record, salidas, ganancia) |
| `infra.py` | Arranque de OBS, salud del servidor, encendido remoto |
| `recorder.py` | Grabación (OBS) + subida + nota |
| `queue_worker.py` | Cola FIFO persistente, reintentos, borrado del local |
| `icons.py` | Iconos de bandeja en runtime |
| `settings_window.py` | Ventana de ajustes (Qt) |
| `actas_list.py` | Diálogo "Ver mis actas" |
| `hotkey.py` | Hotkey global Ctrl+Alt+R (Windows) |
| `app.py` | App de bandeja, menú, worker, notificaciones, single-instance |
| `run.py` | Entrypoint para PyInstaller |
