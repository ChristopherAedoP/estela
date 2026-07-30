# Puesta en marcha — Estela

Guía para dejar Estela funcionando desde cero partiendo de un clon del repositorio.
Si solo quieres entender cómo está construido, lee antes [architecture.md](architecture.md).

## Antes de empezar: elige tu topología

Estela son **dos piezas separadas**: un cliente que graba y un servidor que transcribe con
GPU. Puedes ponerlas en la misma máquina o en máquinas distintas.

| Topología | Cuándo usarla | Qué necesitas |
|---|---|---|
| **Todo en un PC** (recomendada para empezar) | Tienes un PC Windows con GPU NVIDIA | Un solo equipo |
| **Cliente + servidor remoto** | El PC donde grabas no tiene GPU, o quieres que el trabajo pesado corra en otra máquina | Un PC para grabar y un servidor Linux con GPU |

Esta guía cubre primero el caso **todo en un PC**, que es el camino más corto para probarlo.
La sección [Variante: servidor en otra máquina](#variante-servidor-en-otra-máquina) explica
las diferencias.

## Requisitos

### Hardware

- **GPU NVIDIA con CUDA.** Es un requisito real, no una recomendación: el servidor viene
  configurado con `ACTAS_WHISPER_DEVICE=cuda`. Sin GPU tendrás que cambiarlo a `cpu`, y la
  transcripción pasa de minutos a bastante más.
- **VRAM**: en el equipo de referencia del autor (RTX 3060, 12 GB) el LLM y Whisper no
  caben simultáneamente, por lo que el pipeline descarga el modelo de Ollama antes de
  cargar Whisper (ver [server.md](server.md)). Con 16 GB o más el margen es cómodo.
- **Disco**: alrededor de 15 GB para los modelos (Whisper large-v3 y el LLM del resumen),
  como orden de magnitud. El tamaño exacto depende del modelo que elijas.

### Software

| Componente | Para qué | Notas |
|---|---|---|
| Python 3.12 | Cliente y servidor | |
| [Ollama](https://ollama.com/download) | Resumen con LLM local | |
| [OBS Studio](https://obsproject.com/) | Capturar el audio del sistema | Solo en la máquina donde grabas |
| Driver NVIDIA con CUDA 12.x | faster-whisper y torch | |

OBS **solo** hace falta para grabar. Si únicamente quieres probar el servidor con un audio
que ya tengas, puedes saltártelo.

## Paso 1 — Servidor

Hay dos caminos. **Con Docker** te ahorras el entorno virtual, las librerías de CUDA y la
versión de Python; solo necesitas Docker y el
[NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)
para que el contenedor vea la GPU:

```bash
docker compose up                 # servidor + Ollama
docker compose up actas-server    # solo el servidor, si ya tienes Ollama
```

Con eso el servidor queda escuchando en el puerto 8770 y puedes **saltar a los pasos 2 y 3
solo para elegir modelo**, y de ahí al paso 5. El resto de este paso es la instalación
manual.

**Sin Docker:**

```powershell
cd server
python -m venv .venv
```

Instala primero torch con soporte CUDA. Las ruedas de PyPI no sirven: en Linux arrastran
otra versión de CUDA y en Windows vienen sin ella.

```powershell
.\.venv\Scripts\pip install torch==2.6.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cu124
```

Y luego el servidor con sus dependencias. El extra `[gpu]` añade las librerías de CUDA que
necesita CTranslate2; **omítelo si vas a correr en CPU**, porque no existen para macOS y
harían fallar la instalación:

```powershell
.\.venv\Scripts\pip install ".[gpu]"
```

Comprueba que la GPU se ve desde el venv:

```powershell
.\.venv\Scripts\python -c "import torch; print(torch.cuda.is_available())"
```

Debe imprimir `True`. Si en su lugar aborta con un error de OpenBLAS, ve a
[troubleshooting.md](troubleshooting.md#el-servidor-arranca-pero-transcribe-devuelve-500)
antes de continuar: es un fallo conocido y tiene arreglo de una línea.

## Paso 2 — Modelo de resumen

El servidor delega el resumen en Ollama. Descarga el modelo que vayas a usar:

```powershell
ollama pull gemma4:12b-it-qat
ollama list
```

`gemma4:12b-it-qat` es el valor por defecto en `server/app/config.py`. Puedes usar otro
(por ejemplo `gemma3:12b`) declarándolo en `ACTAS_OLLAMA_MODEL`; el nombre debe coincidir
**exactamente** con uno de los que aparecen en `ollama list`. Si el modelo configurado no
está descargado, la transcripción funciona pero el acta sale marcada con
`resumen: pendiente`.

Whisper y pyannote no se descargan a mano: se bajan solos la primera vez que se usan, así
que la primera transcripción tarda bastante más que las siguientes.

## Paso 3 — Configuración del servidor

Copia el ejemplo y edítalo. El `.env` real no se versiona:

```powershell
copy .env.example .env
```

Para arrancar no hace falta cambiar nada: las rutas de audio y temporales se resuelven
solas según la plataforma, y el dispositivo de inferencia se detecta (CUDA si hay GPU, CPU
si no). Lo único que conviene revisar es el modelo del resumen:

```ini
ACTAS_OLLAMA_MODEL=gemma4:12b-it-qat
```

Si quieres archivar el audio en otro sitio, por ejemplo un disco de red, fija
`ACTAS_AUDIO_DIR`.

Sobre la **diarización** (quién dice cada cosa): usa `pyannote/speaker-diarization-3.1`, un
modelo con licencia restringida en Hugging Face. Para activarla necesitas aceptar las
licencias del modelo en HF y poner un token de lectura en `ACTAS_HF_TOKEN`. Si dejas el
token vacío, **el pipeline no falla**: transcribe y resume igual, simplemente sin separar
hablantes. Es perfectamente razonable empezar así.

La lista completa de variables está en [configuration.md](configuration.md).

## Paso 4 — Arrancar el servidor y comprobarlo

El código **no carga el `.env` por sí solo** (en producción las variables las inyecta
systemd). Al arrancarlo a mano hay que cargarlas antes:

```powershell
cd server
Get-Content .env | Where-Object { $_ -match '^\s*ACTAS_' } | ForEach-Object {
    $k,$v = $_ -split '=',2
    [System.Environment]::SetEnvironmentVariable($k.Trim(), $v.Trim(), 'Process')
}
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8770
```

En otra terminal:

```powershell
curl http://127.0.0.1:8770/health
```

Debe responder `{"status":"ok"}`.

> **Cuidado con este health check.** Solo dice que el proceso HTTP está vivo; no ejercita
> el pipeline. Un servidor que responde `ok` puede fallar igualmente al transcribir, porque
> `torch`, faster-whisper y pyannote se importan de forma perezosa dentro de la petición.
> La excepción es PyAV, que sí se importa al arrancar: si falta, el servidor no levanta y
> `/health` no responde en absoluto. La prueba de verdad es el paso siguiente.

Prueba real con un audio cualquiera (vale un `.wav`, `.mka`, `.m4a`...):

```powershell
curl -X POST http://127.0.0.1:8770/transcribe -F "audio=@ruta\a\tu\audio.wav" -F "title=prueba"
```

Devuelve un JSON con `filename`, `markdown`, `audio_path` y `duration_sec`. Si ves el
markdown del acta, el servidor está completo. Audios de menos de 1 KB se rechazan con un
400 a propósito.

## Paso 5 — Cliente

```powershell
cd client-py
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt -r requirements-dev.txt
pwsh -File build.ps1
```

`requirements-dev.txt` trae `pyinstaller` (para compilar) y `pytest` (para los tests del
final de esta guía). El cliente no los necesita para funcionar.

Genera `dist\Estela.exe`. También puedes ejecutarlo sin compilar con
`.\.venv\Scripts\python -m actas`.

## Paso 6 — OBS

Estela controla OBS por WebSocket para grabar el audio del sistema; así evita depender de
cables de audio virtuales.

1. Abre OBS y activa **Herramientas → Configuración de WebSocket Server**. Anota la
   contraseña.
2. Importa el perfil y la escena de ejemplo de `client-py/obs-config/` (instrucciones en el
   README de esa carpeta).
3. La escena debe contener **solo** la fuente de audio. Si añades una fuente de vídeo, el
   `.mka` resultante lleva vídeo y la transcripción falla.

## Paso 7 — Configurar y usar el cliente

Arranca `Estela.exe`: aparece en la bandeja del sistema. Clic derecho → **Ajustes**:

- **Servidor**: `http://localhost:8770` si lo corres todo en el mismo PC.
- **Vault**: la carpeta de tu vault de Obsidian y, dentro, la subcarpeta de actas.
- **Audio**: pulsa "Detectar salidas" y elige la salida por la que realmente suena.
- **Ganancia**: las salidas HDMI y de monitor se capturan notablemente más bajo por WASAPI
  loopback. Súbela a unos 20 dB. En las pruebas del autor ese valor no degradó la
  transcripción; si el audio de origen ya viene fuerte, bájala para no saturar.

La configuración se guarda en `%APPDATA%\Actas\config.json`, fuera del repositorio.

### Uso diario

- **Ctrl+Alt+R** inicia y detiene la grabación. También sirve el clic en el icono.
- Al detener, pide un título y **encola** el trabajo. La app vuelve a estar libre de
  inmediato: puedes grabar otra reunión mientras la anterior se procesa.
- El icono indica el estado: gris inactivo, rojo grabando, ámbar procesando.
- Cuando termina, escribe el acta en tu vault y borra el `.mka` local.
- Menú del icono: ver actas, abrir la carpeta, ajustes, reintentar fallidos, salir.

La cola es persistente (`%APPDATA%\Actas\queue.json`): si cierras la app con trabajos
pendientes, se retoman al abrirla. Los fallos transitorios se reintentan solos; los
permanentes (audio vacío o corrupto) se descartan.

## Variante: servidor en otra máquina

Los pasos 1 a 4 se ejecutan en el servidor Linux con GPU en lugar de en el PC, adaptando
los comandos (`.venv/bin/pip` en vez de `.\.venv\Scripts\pip`, `cp` en vez de `copy`).
Diferencias importantes:

- Las rutas por defecto se resuelven igual de bien en Linux, así que tampoco hay que
  tocarlas. Si quieres archivar el audio en un montaje de red, fija `ACTAS_AUDIO_DIR`.
- **Dónde va el `.env`**: en el modo local el servidor lee `server/.env`. Bajo systemd
  **no**: el unit declara `EnvironmentFile=-/etc/actas-server.env`, así que el archivo va
  ahí. `deploy.ps1` no lo copia (a propósito: contiene el token de HF).
- **`deploy.ps1` solo actualiza el código** (`app/`, `tests/`, `pyproject.toml`,
  `pytest.ini`, el unit y el guion de arranque) sobre un servidor **ya provisionado**. La
  primera vez hay que crear a mano el destino, el venv, el usuario del servicio y
  `/etc/actas-server.env`, e instalar el unit; `systemctl restart actas-server` falla si el
  unit no está instalado todavía.
- **Usuario del servicio**: el unit trae `User=actas`. Créalo
  (`sudo useradd --system --home /opt/actas-server actas`) o cambia el valor al usuario
  propietario del venv, que además debe poder escribir en `ACTAS_AUDIO_DIR`.
- **Configuración**: bajo systemd todas las variables van en `/etc/actas-server.env`, no en
  `server/.env`. `deploy.ps1` no lo copia a propósito, porque lleva el token de Hugging
  Face.
- El arranque usa `actas-server-start.sh`, que resuelve `LD_LIBRARY_PATH` preguntándole al
  intérprete del venv. Así la versión de Python no queda cableada en el unit.
- El unit ya arranca uvicorn en `0.0.0.0:8770`, necesario para que el cliente lo alcance
  desde otra máquina.
- En el cliente, **Servidor** apunta a `http://<host>:8770`.

El cliente admite además un **respaldo automático**: si el servidor principal no responde,
puede arrancar y usar un servidor local en el propio PC sin que tengas que tocar nada. Se
configura con `local_server_url`, `auto_start_local` y `local_server_dir`, y la cascada
completa está descrita en [client.md](client.md#servidor-primario-nas-con-respaldo-local).

## Comprobar que todo está bien

```powershell
# Tests del servidor
cd server; .\.venv\Scripts\python -m pytest tests\ -q

# Tests del cliente
cd client-py; .\.venv\Scripts\python -m pytest tests\ -q
```

## Si algo falla

Empieza por [troubleshooting.md](troubleshooting.md). Los tres sitios donde mirar:

1. Log del cliente: `%APPDATA%\Actas\actas.log`.
2. Salida del servidor (la consola de uvicorn, o `journalctl -u actas-server` en systemd).
3. `curl http://127.0.0.1:8770/health`, recordando que un `ok` no garantiza que el pipeline
   funcione.
