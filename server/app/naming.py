"""Nombres de archivo seguros a partir de titulos escritos por el usuario.

El titulo de una reunion lo escribe una persona y acaba usandose como nombre de
archivo en dos sitios: el audio archivado en el servidor y la nota que el cliente
guarda en el vault. Sin sanear, un titulo con ':' falla en Windows y uno con '/'
o '..' permite escribir fuera del directorio previsto.
"""
import re
import unicodedata

# Caracteres que Windows prohibe en un nombre de archivo, incluidos los
# separadores de ruta de ambos sistemas.
_ILLEGAL = set('<>:"/\\|?*')


def slugify(text: str) -> str:
    """Nombre tecnico: sin acentos, en minusculas y separado por guiones.

    Se usa para el audio archivado, donde prima que el nombre sea predecible.
    """
    norm = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    norm = re.sub(r"[^\w\s-]", "", norm).strip().lower()
    return re.sub(r"[\s_-]+", "-", norm) or "reunion"


def safe_note_name(text: str) -> str:
    """Nombre de la nota: legible para el usuario y valido como archivo.

    A diferencia de slugify conserva acentos, mayusculas y espacios, porque es el
    nombre que se vera en el vault de Obsidian.

    Es ademas la barrera que impide que el nombre devuelto por el servidor haga
    que el cliente escriba fuera de su carpeta de actas: el cliente lo usa tal
    cual para construir la ruta del archivo.
    """
    cleaned = "".join(" " if (c in _ILLEGAL or ord(c) < 32) else c for c in text)
    # Una secuencia '..' permitiria subir de directorio.
    cleaned = re.sub(r"\.{2,}", ".", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    # Windows rechaza los nombres terminados en punto o espacio.
    cleaned = cleaned.strip(". ")
    return cleaned or "Reunion"
