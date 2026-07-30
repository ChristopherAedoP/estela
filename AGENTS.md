# AGENTS.md — Guía para agentes de IA (Estela)

Contexto y reglas para trabajar en este proyecto con agentes (Claude, etc.).

## Reglas obligatorias (Git)

- **NUNCA hacer push directo a `main`.** La rama `main` está protegida por convención.
- **Todo cambio entra por Pull Request.** Flujo:
  1. Crear una rama desde `main`: `git switch -c feat/<descripcion>` (o `fix/...`, `docs/...`, `chore/...`).
  2. Commitear en esa rama (Conventional Commits, en español).
  3. Push de la rama: `git push -u origin <rama>`.
  4. Abrir PR: `gh pr create --base main --fill` (revisar `gh pr view` antes).
  5. El merge a `main` se hace vía PR (revisado), nunca con push local a `main`.
- No usar `git push --force` sobre `main`.
- No commitear secretos ni datos de infraestructura (ver más abajo).

## Documentación del proyecto

La documentación vive en [`docs/`](docs/). Consultarla y mantenerla actualizada:

- [`docs/architecture.md`](docs/architecture.md) — Arquitectura con diagramas C4 (Mermaid) + flujo.
- [`docs/server.md`](docs/server.md) — Servidor: pipeline, modelos, VRAM, deploy, tests.
- [`docs/client.md`](docs/client.md) — Cliente: app de bandeja, OBS, ganancia, cola.
- [`docs/troubleshooting.md`](docs/troubleshooting.md) — Problemas conocidos y sus soluciones.
- [`docs/decisions.md`](docs/decisions.md) — Decisiones técnicas (ADRs).
- [`docs/roadmap.md`](docs/roadmap.md) — Roadmap de mejoras (usabilidad y funcionalidad).

Además: `README.md` (portada) y `CHANGELOG.md` (historial). Si un cambio afecta a la
arquitectura, el comportamiento o la operación, **actualizar la doc correspondiente en el
mismo PR**.

## Qué es Estela

Herramienta de **grabación y transcripción de reuniones con IA local**. Cliente de
escritorio (app de bandeja Python/PySide6) + servidor FastAPI que corre en una máquina
con GPU. Genera actas markdown en un vault Obsidian. Ver `README.md` y `docs/`.

## Estructura

```
estela/
├── client-py/        # Cliente Python/PySide6 (app de bandeja) -> Estela.exe
│   ├── actas/        # paquete python (nombre interno historico)
│   ├── obs-config/   # config OBS de ejemplo (perfil + escena)
│   ├── config.example.json
│   └── build.ps1     # compila Estela.exe (PyInstaller)
├── server/           # Servidor FastAPI -> se despliega en la maquina con GPU
│   ├── app/          # modulos del pipeline
│   ├── tests/        # pytest
│   └── .env.example  # variables de entorno del servidor
├── deploy.ps1        # sincroniza server/ al host por scp (parametrizado por env)
└── docs/             # documentacion detallada
```

## Nombre: "Estela" vs "actas"

- **Estela** = nombre del producto (repo, README, app, `Estela.exe`).
- **actas** = identificador técnico interno que NO se renombra (para no romper despliegues
  existentes): paquete python `actas`, servicio `actas-server`, paths internos y variables
  `ACTAS_*` del servidor.
- Respetar esta separación al editar. No renombrar lo interno sin un plan de migración.

## Principio de configuración (importante)

- **El código NO contiene configuración de infraestructura ni secretos.**
- **Cliente**: defaults neutros en `config.py`; la config real la introduce el usuario en
  la ventana de Ajustes y se persiste en `config.json` del directorio de datos del usuario
  (fuera de git). Ver `config.example.json`.
- **Servidor**: todo por **variables de entorno** (`ACTAS_*`), cargadas desde un archivo
  `.env` en el servidor (fuera de git). Ver `server/.env.example`.
- `deploy.ps1` se parametriza con variables de entorno (`ESTELA_DEPLOY_HOST`, etc.). No
  hardcodear hosts ni passwords.

## Infraestructura (genérica)

| Recurso | Detalle |
|---------|---------|
| Servidor | Máquina/VM con GPU NVIDIA (>=12GB VRAM recomendado), Linux |
| Acceso | SSH por clave; sudo (idealmente NOPASSWD para deploy) |
| Servicio | `actas-server.service` (systemd, puerto 8770) |
| Modelos | Whisper `large-v3`, pyannote `speaker-diarization-3.1`, LLM en Ollama |
| Vault | Carpeta del vault Obsidian (configurable por el usuario) |
| Audio archivado | Carpeta del servidor (ej. montaje NFS), via `ACTAS_AUDIO_DIR` |

## Comandos frecuentes

```powershell
# --- Cliente ---
cd client-py
pwsh -File build.ps1                       # compilar Estela.exe

# --- Servidor (configura $env:ESTELA_DEPLOY_HOST = "usuario@host") ---
pwsh -File deploy.ps1                       # desplegar server al host
ssh <user@host> "systemctl is-active actas-server"
ssh <user@host> "sudo systemctl restart actas-server"
ssh <user@host> "cd /opt/actas-server && .venv/bin/python -m pytest tests/ -q"
curl http://<host>:8770/health

# --- Logs ---
# Cliente: <dir-datos-usuario>/Estela/actas.log
ssh <user@host> "sudo journalctl -u actas-server -n 50 --no-pager"
```

## Convenciones

- **Git/PR**: ver "Reglas obligatorias (Git)" arriba. Trabajar siempre en una rama y
  abrir PR; nunca push directo a `main`.
- **Sin emojis**: no usar emojis en código, documentación, commits, comentarios ni en
  ningún archivo del proyecto.
- **Commits**: Conventional Commits con scope (`feat(estela): ...`, `fix(actas): ...`),
  en español, descriptivos.
- **TDD en el server**: test → ver fallar → implementar → ver pasar. Tests en
  `server/tests/`, correr con pytest en el servidor (necesitan el venv con deps).
- **Cambios en el server**: editar en `server/`, desplegar con `deploy.ps1`, reiniciar el
  servicio. El repo es la fuente de verdad; el servidor es un despliegue.
- **No commitear**: `.venv/`, `dist/`, `build/`, `*.env`, `config.json` real,
  `device.txt`, `deploy.ps1` con datos reales, `*.wav`, `*.mka` (ver `.gitignore`).
- **Gestión de VRAM**: el LLM y Whisper no caben juntos en GPUs de ~12GB. Respetar la
  orquestación de `vram.py` (descargar el LLM de Ollama antes de cargar Whisper).
- **Nunca** poner IPs, hostnames, passwords ni rutas personales en el código ni en docs.

## Verificación antes de dar algo por hecho

- Correr `pytest` en el servidor y confirmar verde.
- Validar el pipeline con un audio real (no solo unit tests).
- Confirmar `health: ok` del servidor.
- Cliente: que `Estela.exe` arranque y la app viva en la bandeja.
