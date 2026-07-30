# Cliente (app de bandeja) — Estela

App de escritorio Python/PySide6 que vive en la bandeja del sistema. Compila a `Estela.exe`.

## Estados del icono

- **Gris**: inactivo.
- **Rojo**: grabando.
- **Ámbar**: procesando en background (cola).

Grabar y procesar están **desacoplados**: al detener una grabación se encola y la app queda
libre para grabar otra al instante. La cola procesa 1 a 1 en background.

## Uso

- **Ctrl+Alt+R** (hotkey global) o clic en el icono: iniciar / detener.
- Al detener, pide el título y encola el trabajo.
- Menú (clic derecho): Ver mis actas, Abrir carpeta de actas, Ajustes, Reintentar fallidos, Salir.

## Captura con OBS

La app controla OBS por WebSocket (obs-websocket v5). OBS graba **solo-audio** (.mka) de la
salida elegida. Config de OBS de ejemplo en `client-py/obs-config/` (perfil + escena).

- **Elegir salida**: Ajustes → "Detectar salidas" → seleccionar.
- **Ganancia**: las salidas HDMI/NVIDIA (parlantes de monitor) se capturan muy bajo; subir
  la "Ganancia de audio" a ~20 dB. No baja la calidad de transcripción (Whisper usa 16kHz).
- La escena debe tener **solo** la fuente de audio (no agregar captura de video).

## Servidor: primario (NAS) con respaldo local

El cliente resuelve qué servidor usar en cada trabajo con una cascada
(`infra.resolve_server`):

1. **Servidor primario** (`server_url`, p. ej. la VM del NAS) si responde `/health`.
2. Si `auto_start_vm`: **encender la VM** por SSH y esperar a que responda.
3. **Servidor local** (`local_server_url`, `http://localhost:8770`) si responde.
4. Si `auto_start_local`: **arrancar Ollama + actas-server local** y usarlo.

El primer servidor disponible procesa el trabajo. Así la grabación se transcribe contra el
NAS cuando está encendido y contra el PC local cuando no, sin cambiar la configuración.

Para el arranque local, `local_server_dir` apunta a la carpeta del server (con `.venv` y
`.env`); Ollama se levanta si `local_ollama_url` no responde.

## Configuración

Defaults neutros en el código; la config real se edita en **Ajustes** y se guarda en el
directorio de datos del usuario (`config.json`), fuera de git. Ver `config.example.json`.

Campos: servidor primario, servidor local + arranque automático + carpeta del server local,
vault, carpeta de actas, host/VM para encendido automático, OBS (url/password/exe/fuente),
dispositivo de audio, ganancia, carpeta de grabaciones, título por defecto, borrar local
tras subir.

Datos de la app (directorio de datos del usuario): `config.json`, `queue.json` (cola
persistente), `actas.log`.

## Cola de procesamiento

- FIFO persistente (`queue.json`): si cierras la app con trabajos pendientes, se retoman.
- Reintento automático de fallidos cuando el servidor vuelve a responder.
- Single-instance: solo corre una app (evita conflictos de cola).
- Borra el `.mka` local tras subir con éxito (el audio queda archivado en el servidor).

## Compilar

```powershell
cd client-py
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt -r requirements-dev.txt
pwsh -File build.ps1     # genera dist\Estela.exe
```

## Arranque con Windows

Crear un acceso directo a `dist\Estela.exe` en la carpeta `shell:startup`.
