# Configuración de OBS para Actas

Config del perfil y escena de OBS que usa el cliente Actas. Graba **solo audio**
(sin video) en `.mka`, AAC mono 128 kbps — liviano y suficiente para transcribir.

## Instalación manual

Copiar a la carpeta de OBS (`%APPDATA%\obs-studio` en Windows):

```
profile\basic.ini   ->  %APPDATA%\obs-studio\basic\profiles\Actas\basic.ini
scene\Actas.json    ->  %APPDATA%\obs-studio\basic\scenes\Actas.json
```

Y en `%APPDATA%\obs-studio\user.ini`, sección `[Basic]`:
```
Profile=Actas
ProfileDir=Actas
SceneCollection=Actas
SceneCollectionFile=Actas.json
```

Además, habilitar el WebSocket en
`%APPDATA%\obs-studio\plugin_config\obs-websocket\config.json`:
```json
{ "server_enabled": true, "server_port": 4455, "auth_required": true,
  "server_password": "<password-del-websocket-de-obs>" }
```

## Detalles técnicos (validados con el código fuente de OBS)

Grabación **solo audio** mediante el output **Custom FFmpeg** (`RecType=FFmpeg`):

| Clave (`[AdvOut]`) | Valor | Motivo |
|--------------------|-------|--------|
| `RecType` | `FFmpeg` | Output custom FFmpeg (permite audio-only) |
| `FFFormat` | `matroska` | Contenedor |
| `FFExtension` | `mka` | Matroska audio |
| `FFVBitrate` | `0` | **Desactiva el video** (la clave del ahorro) |
| `FFVEncoder` | (vacío) | Sin encoder de video |
| `FFAEncoder` | `aac` | Audio AAC |
| `FFABitrate` | `128` | 128 kbps (no afecta la transcripción) |
| `FFAudioMixes` | `1` | Graba el track de audio 1 |
| `[Audio] ChannelSetup` | `Mono` | Voz: mono basta, ahorra ~50% |

Resultado: ~0.5–1 MB/min (antes ~40 MB/min con video). Whisper remuestrea a
16 kHz mono internamente, así que 128 kbps mono mantiene la transcripción intacta.

> La fuente de captura es `wasapi_output_capture` ("Audio Escritorio (Actas)").
> El dispositivo de salida a grabar se elige desde Ajustes de la app (setup).
