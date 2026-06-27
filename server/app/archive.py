import os
import re
import shutil
import unicodedata
from app.config import config


def _slug(text: str) -> str:
    norm = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    norm = re.sub(r"[^\w\s-]", "", norm).strip().lower()
    return re.sub(r"[\s_-]+", "-", norm) or "reunion"


def archive_audio(src_path: str, title: str, date: str, ext: str = "mka") -> str:
    os.makedirs(config.audio_dir, exist_ok=True)
    name = f"{date}_{_slug(title)}.{ext.lstrip('.')}"
    dest = os.path.join(config.audio_dir, name)
    shutil.copy2(src_path, dest)
    return dest
