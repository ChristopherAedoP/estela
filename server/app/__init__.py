"""Paquete del actas-server.

Aqui se acotan los hilos de las librerias de algebra lineal, ANTES de que
cualquier modulo llegue a importar torch o faster-whisper.

Por defecto estas librerias abren un hilo por nucleo logico y reservan buffers
por hilo. En equipos con muchos nucleos, o con la memoria comprometida por otras
cargas, esa reserva falla y tumba el proceso:

  - OpenBLAS (torch): "Memory allocation still failed after 10 retries", que
    aborta el proceso al importar torch.
  - MKL (CTranslate2, el motor de faster-whisper): "mkl_malloc: failed to
    allocate memory" al construir el modelo, incluso con device=cuda.

Ambos enganan porque no dependen de la RAM libre, sino de la memoria
comprometible del sistema: ocurren con decenas de GB de RAM disponibles.

No se pisa ningun valor que el usuario ya haya definido.
"""
import os

_threads = str(min(8, os.cpu_count() or 8))
for _var in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_var, _threads)
