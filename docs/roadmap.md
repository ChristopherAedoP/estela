# Roadmap — Estela

Mejoras de usabilidad y funcionalidad identificadas tras un análisis del sistema (cliente
PySide6 + servidor FastAPI). Estado actual: **funcional (v1.0.0)**. Este documento NO fija
prioridades definitivas; agrupa las mejoras por categoría y propone fases sugeridas.

Cada item indica: descripción, problema actual (con referencia al archivo/función), impacto
y esfuerzo estimado.

## A. Robustez y datos (evitar pérdida silenciosa)

| ID | Mejora | Problema actual | Impacto | Esfuerzo |
|----|--------|-----------------|---------|----------|
| A1 | Escritura atómica de config y cola | `Config.save` (config.py) y `ProcessingQueue._save` (queue_worker.py) reescriben el JSON sin `tmp+os.replace`. Un crash a media escritura corrompe el archivo y `load()`/`_load()` lo descartan en silencio, perdiendo config o toda la cola. | Alto | Bajo |
| A2 | Límite de reintentos + estado "fallido definitivo" | `_process_job` reintenta todo `RecorderError` cada 30s sin tope (queue_worker.py). Un `.mka` borrado o un error no transitorio entra en bucle eterno. | Alto | Bajo |
| A3 | Clasificar errores HTTP correctamente | En `recorder._upload`, `raise_for_status()` convierte un 400 (audio inválido) en error tratado como transitorio → reintento infinito. Debería ser permanente. | Medio | Bajo |
| A4 | Detectar audio silencioso (no solo vacío) | El guard solo mira tamaño `< 1024 bytes` (recorder.py). Un `.mka` grande pero mudo pasa y genera un acta inútil. | Medio | Medio |
| A5 | No borrar el `.mka` en fallo permanente | En `PermanentError` se borra la grabación local (queue_worker.py), perdiendo el audio sin poder inspeccionarlo. | Medio | Bajo |

## B. Usabilidad de la app

| ID | Mejora | Problema actual | Impacto | Esfuerzo |
|----|--------|-----------------|---------|----------|
| B1 | Ajustes completos para onboarding | La ventana de Ajustes (settings_window.py) no expone `obs_password`, `obs_url`, `obs_exe`, `obs_input_name` ni `recordings_dir`. Un usuario nuevo no puede configurar OBS sin editar `config.json` a mano. | Alto | Bajo |
| B2 | Ventana de cola (gestión por-trabajo) | Solo existe "Reintentar fallidos" global (app.py / queue_worker.py). Falta ver cada job con su estado/error y poder cancelar, eliminar o reintentar uno. | Alto | Medio |
| B3 | Temporizador de grabación | Ni el tooltip ni el menú (app.py `_update_tooltip`) muestran cuánto llevas grabando. | Medio | Bajo |
| B4 | Auto-refresco del listado de actas | "Ver mis actas" (actas_list.py) no escucha `queue.job_done`; hay que pulsar "Actualizar" para ver un acta nueva. | Medio | Bajo |
| B5 | Acceso a diagnóstico desde el menú | No hay "Ver registro" ni "Abrir carpeta de datos" (app.py `_build_menu`). Para un `.exe` sin consola es clave para soporte. | Medio | Bajo |
| B6 | Rotación del log | `actas.log` (log.py) crece sin límite (FileHandler plano). | Bajo | Bajo |
| B7 | Validación de prerrequisitos antes de grabar | Permite grabar sin `vault_path`/servidor configurado (app.py `_start`); el fallo aparece tarde, al escribir la nota o subir. | Medio | Bajo |
| B8 | Progreso real de subida + timeout configurable | `recorder._upload` es bloqueante, timeout fijo 1800s, sin callback de bytes; `read_bytes()` carga todo en RAM (problema en reuniones largas). | Medio | Medio |
| B9 | Listado de actas desacoplado del naming | El glob `"Acta *.md"` (actas_list.py) oculta cualquier nota cuyo nombre no empiece por "Acta ". Listar por extensión/carpeta. | Bajo | Bajo |

## C. Funcionalidad del producto (valor nuevo)

| ID | Mejora | Descripción | Impacto | Esfuerzo |
|----|--------|-------------|---------|----------|
| C1 | Identificar/nombrar hablantes | Hoy son `Hablante 1/2/3`. Mapear a nombres reales: manual post-acta, huellas de voz (embeddings de pyannote) o cruce con la app de origen (p.ej. Discord). | Alto | Medio-Alto |
| C2 | Plantillas de acta configurables | El prompt y las secciones (Resumen/Puntos/Decisiones/Tareas) están hardcodeados en summarize.py. Permitir plantillas por tipo de reunión (daily, 1:1, retro, clase). | Alto | Medio |
| C3 | Exportar tareas | Las tareas se extraen pero quedan en el `.md`. Exportarlas a un archivo de tareas del vault o a un gestor externo. | Medio | Medio |
| C4 | Word-level timestamps | Mejor precisión de "quién dijo qué" (alineación tipo WhisperX). Requiere WhisperX completo → actualizar CUDA de la VM (riesgo a otros servicios de la GPU). | Medio | Alto |
| C5 | Resumen por hablante / detección de idioma | Resumen de lo que aportó cada hablante; o auto-detectar idioma en vez de fijar `es` (config.py `language`). | Medio | Medio |
| C6 | Apagado automático de la VM | La app enciende la VM (`infra.start_vm`) pero no la apaga. Apagarla tras vaciar la cola para ahorro energético. | Medio | Bajo |

## D. Operación / DevEx

| ID | Mejora | Descripción | Impacto | Esfuerzo |
|----|--------|-------------|---------|----------|
| D1 | IPC en segunda instancia | `_acquire_single_instance` (app.py) solo bloquea; usar el `QLocalServer` existente para "traer al frente" o disparar acción en la instancia viva. | Bajo | Bajo |
| D2 | Hotkey configurable + multiplataforma | Ctrl+Alt+R está hardcodeado y solo funciona en Windows (hotkey.py). Hacerlo configurable y soportar mac/Linux. | Bajo | Medio |
| D3 | CI (tests en cada PR) | Ejecutar `pytest` del servidor automáticamente en GitHub Actions al abrir/actualizar PR. | Medio | Bajo |
| D4 | Observabilidad del servidor | Ampliar `/health` (modelos cargados, VRAM disponible, versión) para diagnóstico. | Bajo | Bajo |

## Fases sugeridas (no vinculantes)

Orden propuesto para maximizar valor con bajo riesgo. La prioridad final la decide el dueño
del proyecto.

1. **Fase 1 — Estabilidad y confianza:** A1, A2, A3, A4, A5, B1, B5, B6.
   Que nunca pierda datos y que un usuario nuevo pueda configurarlo sin tocar JSON.
2. **Fase 2 — Control y feedback:** B2, B3, B4, B7, B8, B9.
   Gestión de cola, temporizador, validaciones, progreso.
3. **Fase 3 — Valor del producto:** C2, C1, C6, C5.
   Plantillas, nombres de hablantes, apagado de VM, resumen por hablante.
4. **Fase 4 — Pulido / DevEx:** C3, C4, D1, D2, D3, D4.
   Integraciones, alineación por palabra y calidad de proyecto.

## Notas

- Las mejoras de la categoría A no aportan funciones visibles, pero son la base de confianza
  del sistema: conviene abordarlas temprano.
- C1 (nombrar hablantes) y C4 (word-level timestamps) ya se evaluaron; ver
  [decisions.md](decisions.md) para el contexto (WhisperX y el límite de CUDA).
- Cada item, al implementarse, sigue el flujo del proyecto: rama + PR, tests (TDD en el
  servidor) y actualización de la doc correspondiente (ver [AGENTS.md](../AGENTS.md)).
