# Imagen del actas-server.
#
# Se parte de python:slim y las librerias de CUDA se instalan por pip
# (nvidia-cublas-cu12 / nvidia-cudnn-cu12) en vez de usar una imagen base de
# CUDA: pesa bastante menos y evita tener que casar la version de CUDA de la
# imagen con la del host. El driver lo aporta el host a traves del NVIDIA
# Container Toolkit.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# libgomp1: runtime de OpenMP que necesitan torch y CTranslate2.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv/actas

# torch se instala primero desde el indice de CUDA 12.4. Las ruedas de PyPI no
# sirven: en Linux arrastran otra version de CUDA y en Windows vienen sin ella.
RUN pip install torch==2.6.0 torchaudio==2.6.0 \
    --index-url https://download.pytorch.org/whl/cu124

COPY pyproject.toml ./
COPY app ./app
RUN pip install ".[gpu]"

# CTranslate2 carga cuBLAS y cuDNN desde los paquetes pip de nvidia. La ruta
# lleva la version de Python, que aqui esta fijada por la imagen base, asi que no
# puede desincronizarse como ocurre en una instalacion manual.
ENV LD_LIBRARY_PATH=/usr/local/lib/python3.12/site-packages/nvidia/cublas/lib:/usr/local/lib/python3.12/site-packages/nvidia/cudnn/lib

# Rutas dentro del contenedor. Se montan como volumenes para que el audio
# archivado y los modelos descargados sobrevivan a la recreacion del contenedor.
ENV ACTAS_AUDIO_DIR=/data/audio \
    ACTAS_TMP_DIR=/tmp/estela \
    HF_HOME=/data/models
RUN mkdir -p /data/audio /data/models

EXPOSE 8770

# Comprobacion barata a proposito: el chequeo profundo (/health?deep=1) importa
# los modelos y tardaria demasiado para un healthcheck periodico.
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8770/health').read()"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8770"]
