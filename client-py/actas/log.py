"""Logging a archivo (para diagnosticar la app empaquetada sin consola)."""
from __future__ import annotations

import logging

from .config import LOG_PATH


def get_logger() -> logging.Logger:
    logger = logging.getLogger("actas")
    if logger.handlers:
        return logger
    logger.setLevel(logging.DEBUG)
    fh = logging.FileHandler(LOG_PATH, encoding="utf-8")
    fh.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    logger.addHandler(fh)
    return logger
