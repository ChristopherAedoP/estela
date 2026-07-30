# Configuración — Estela

Toda la configuración de Estela vive **fuera del código**: variables de entorno en el
servidor y un archivo JSON en el cliente. El repositorio solo contiene ejemplos.

## Servidor: variables de entorno

Se declaran en un archivo copiado de `server/.env.example` (no versionado). Los valores por
defecto están en `server/app/config.py`.

**Dónde va ese archivo depende del modo de ejecución:**

| Modo | Ubicación | Quién lo lee |
|---|---|---|
| Local (el cliente arranca el servidor, o lo lanzas a mano) | `server/.env` | El propio comando de arranque, o `infra.py` al lanzarlo |
| Servicio systemd | `/etc/actas-server.env` | `EnvironmentFile` del unit `actas-server.service` |

`deploy.ps1` **no** copia el `.env` al servidor remoto: contiene el token de Hugging Face y
se gestiona a mano en la máquina destino.

| Variable | Default | Descripción |
|---|---|---|
| `ACTAS_WHISPER_MODEL` | `large-v3` | Modelo de faster-whisper |
| `ACTAS_WHISPER_DEVICE` | `auto` | `auto`, `cuda` o `cpu`. `auto` usa CUDA si hay GPU |
| `ACTAS_WHISPER_COMPUTE` | `auto` | `auto` resuelve a `float16` en GPU y a `int8` en CPU |
| `ACTAS_LANGUAGE` | `es` | Idioma de la transcripción |
| `ACTAS_OLLAMA_MODEL` | `gemma4:12b-it-qat` | LLM del resumen. Debe estar descargado en Ollama |
| `ACTAS_OLLAMA_URL` | `http://127.0.0.1:11434` | URL de Ollama |
| `ACTAS_HF_TOKEN` | (vacío) | Token de Hugging Face para pyannote. Vacío = sin diarización |
| `ACTAS_AUDIO_DIR` | directorio de datos del usuario | Dónde se archiva el audio original |
| `ACTAS_TMP_DIR` | temporal del sistema | Temporales del pipeline |
| `ACTAS_MIN_SPEAKERS` | (vacío) | Mínimo de hablantes para la diarización |
| `ACTAS_MAX_SPEAKERS` | (vacío) | Máximo de hablantes. Útil si pyannote sobreestima |

Notas importantes:

- **Las rutas por defecto se resuelven por plataforma**: en Windows bajo
  `%LOCALAPPDATA%\estela`, en Linux bajo `$XDG_DATA_HOME` o `~/.local/share/estela`, y los
  temporales en el directorio temporal del sistema. No hace falta tocarlas para arrancar.
  Si quieres archivar el audio en otro sitio (un NAS, por ejemplo), fija `ACTAS_AUDIO_DIR`.
- **El servidor no carga el `.env` automáticamente.** En producción las variables las
  inyecta systemd; al arrancarlo a mano hay que exportarlas antes (ver
  [getting-started.md](getting-started.md#paso-4--arrancar-el-servidor-y-comprobarlo)).
- Sin `ACTAS_HF_TOKEN` el pipeline **no falla**: transcribe y resume, pero no separa
  hablantes.

### Límite de hilos de las librerías de álgebra

El servidor fija `OPENBLAS_NUM_THREADS`, `OMP_NUM_THREADS` y `MKL_NUM_THREADS` al arrancar
si no están definidas, con un tope de 8 hilos. Sin ese tope, en equipos con muchos núcleos
o con la memoria comprometida, la reserva de buffers por hilo falla y tumba el proceso.
Puedes fijarlas tú para sobreescribir el valor. Ver
[troubleshooting.md](troubleshooting.md#el-servidor-arranca-pero-transcribe-devuelve-500).

## Cliente: `config.json`

El cliente guarda su configuración en el directorio de datos del usuario:

| Sistema | Ruta |
|---|---|
| Windows | `%APPDATA%\Actas\` |
| Otros | directorio de datos del usuario equivalente |

En esa misma carpeta viven `config.json`, `queue.json` (la cola persistente) y `actas.log`.
Ninguno se versiona. La referencia de campos está en `client-py/config.example.json`, y
normalmente no hace falta editar el JSON a mano: casi todo se configura desde la ventana de
**Ajustes**.

| Campo | Descripción |
|---|---|
| `server_url` | Servidor principal de transcripción |
| `local_server_url` | Servidor de respaldo en el propio PC |
| `auto_start_local` | Arrancar el servidor local si el principal no responde |
| `local_server_dir` | Carpeta del servidor local. Debe contener el `.venv`; el `.env` es opcional (si falta, se usan los valores por defecto) |
| `local_server_python` | Intérprete concreto. Vacío = usa el del `.venv` de `local_server_dir` |
| `local_ollama_url` | URL de Ollama para el arranque local |
| `vault_path` | Carpeta del vault de Obsidian |
| `actas_dir` | Subcarpeta de actas dentro del vault, o ruta absoluta |
| `proxmox_host`, `vm_id`, `auto_start_vm` | Encendido por SSH de una VM que aloje el servidor |
| `obs_url`, `obs_password`, `obs_exe`, `obs_input_name` | Conexión y fuente de OBS |
| `audio_device_id`, `audio_device_label` | Salida de audio a capturar |
| `audio_gain_db` | Ganancia aplicada a la captura. ~20 dB en salidas HDMI o de monitor |
| `recordings_dir` | Carpeta temporal de los `.mka` antes de subirlos |
| `ask_title`, `default_title` | Comportamiento del diálogo de título |
| `delete_local_after_upload` | Borrar el `.mka` local tras subirlo con éxito |

### Cascada de resolución del servidor

Para cada trabajo, el cliente decide contra qué servidor procesar, en este orden:

1. `server_url` si responde a `/health`.
2. Si `auto_start_vm`, enciende la VM por SSH y espera a que responda.
3. `local_server_url` si responde.
4. Si `auto_start_local`, arranca Ollama y el servidor local y lo usa.

Dos detalles que conviene conocer del arranque local:

- Solo se propagan al servidor local las variables del `.env` cuyo nombre empieza por
  `ACTAS_`. Cualquier otra variable que necesite el proceso (por ejemplo
  `OPENBLAS_NUM_THREADS`) debe estar en el entorno del usuario que ejecuta el cliente.
- El servidor local se lanza como **proceso hijo** del cliente. Si el cliente termina justo
  después de arrancarlo, el servidor local también termina.

## Antes de compartir el repositorio

El repositorio no contiene secretos, pero **tu instalación sí**. Revisa esto antes de
publicarlo o pasárselo a alguien:

| Archivo | Qué contiene | Estado |
|---|---|---|
| `server/.env` | Token de Hugging Face, rutas locales | No versionado. Verifica que sigue en `.gitignore` |
| `%APPDATA%\Actas\config.json` | Contraseña del WebSocket de OBS, ruta de tu vault, IPs internas | Fuera del repositorio |
| `%APPDATA%\Actas\actas.log` | Títulos de tus reuniones, rutas | Fuera del repositorio |
| `client-py/dist/` | Binario compilado | No lo publiques; que cada uno compile el suyo |

Comprobación rápida de que no se ha colado nada:

```powershell
git ls-files | Select-String -Pattern "\.env$|config\.json$|\.log$"
```

No debe devolver nada. Ten en cuenta además que **las actas generadas contienen el
contenido de tus reuniones**: si tu vault de Obsidian está en un repositorio, no lo mezcles
con este.
