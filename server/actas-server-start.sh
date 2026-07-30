#!/bin/sh
# Arranque del actas-server bajo systemd.
#
# Calcula LD_LIBRARY_PATH preguntandoselo al propio interprete del venv, en vez
# de cablear la version de Python en el unit. CTranslate2 (el motor de
# faster-whisper) carga cuBLAS y cuDNN desde los paquetes pip de nvidia, y una
# ruta con la version equivocada produce un "libcublas.so.12 not found" que
# aparenta ser un problema de CUDA del sistema y no lo es.
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
PY="$DIR/.venv/bin/python"

if [ ! -x "$PY" ]; then
    echo "No se encontro el interprete del venv en $PY" >&2
    echo "Crea el entorno con: python -m venv $DIR/.venv && $DIR/.venv/bin/pip install '$DIR[gpu]'" >&2
    exit 1
fi

SITE="$("$PY" -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')"
if [ -d "$SITE/nvidia" ]; then
    LD_LIBRARY_PATH="$SITE/nvidia/cublas/lib:$SITE/nvidia/cudnn/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
    export LD_LIBRARY_PATH
fi

cd "$DIR"
exec "$PY" -m uvicorn app.main:app \
    --host "${ACTAS_HOST:-0.0.0.0}" \
    --port "${ACTAS_PORT:-8770}"
