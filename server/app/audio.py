"""Decodificación de audio a WAV PCM con PyAV.

El cliente sube audio comprimido (AAC/MKA). faster-whisper lo lee vía ffmpeg
interno, pero pyannote usa soundfile/libsndfile, que NO soporta AAC y falla
("Format not recognised"). Por eso decodificamos a WAV PCM 16 kHz mono real
para que la diarización funcione.
"""
from __future__ import annotations

import os
import wave

import av


def decode_to_wav(src_path: str, dst_path: str, sample_rate: int = 16000) -> str:
    """Decodifica cualquier formato de audio a WAV PCM s16 mono a `sample_rate`.

    Devuelve `dst_path`. Usa PyAV (ffmpeg) para leer y resamplear, y escribe un
    WAV estándar legible por soundfile/libsndfile.
    """
    resampler = av.AudioResampler(format="s16", layout="mono", rate=sample_rate)

    with av.open(src_path) as container:
        audio_streams = [s for s in container.streams if s.type == "audio"]
        if not audio_streams:
            raise ValueError(f"El archivo no tiene pista de audio: {src_path}")
        stream = audio_streams[0]

        os.makedirs(os.path.dirname(dst_path) or ".", exist_ok=True)
        with wave.open(dst_path, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)  # s16 = 2 bytes
            wav.setframerate(sample_rate)

            for frame in container.decode(stream):
                for rframe in resampler.resample(frame):
                    wav.writeframes(bytes(rframe.planes[0]))

            # flush del resampler
            for rframe in resampler.resample(None):
                if rframe is not None:
                    wav.writeframes(bytes(rframe.planes[0]))

    return dst_path
