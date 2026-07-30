import os
import shutil
from app.config import config
from app.naming import slugify

__all__ = ["archive_audio", "slugify"]


def archive_audio(src_path: str, title: str, date: str, ext: str = "mka") -> str:
    os.makedirs(config.audio_dir, exist_ok=True)
    name = f"{date}_{slugify(title)}.{ext.lstrip('.')}"
    dest = os.path.join(config.audio_dir, name)
    shutil.copy2(src_path, dest)
    return dest
