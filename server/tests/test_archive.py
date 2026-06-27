import os
import app.archive as archive_mod
from app.archive import archive_audio


def test_archive_copies_to_dest(tmp_path, monkeypatch):
    src = tmp_path / "src.wav"
    src.write_bytes(b"RIFFdata")
    dest_dir = tmp_path / "dest"
    monkeypatch.setattr(archive_mod.config, "audio_dir", str(dest_dir))

    result = archive_audio(str(src), "Reunión equipo", "2026-06-25")

    assert os.path.exists(result)
    assert result.endswith(".mka")   # default actual: archiva el original comprimido
    assert "2026-06-25" in result
    # nombre saneado (sin espacios ni acentos problemáticos)
    assert " " not in os.path.basename(result)


def test_archive_respects_ext(tmp_path, monkeypatch):
    src = tmp_path / "src.bin"
    src.write_bytes(b"data")
    monkeypatch.setattr(archive_mod.config, "audio_dir", str(tmp_path / "dest"))
    result = archive_audio(str(src), "Test", "2026-06-27", ext="wav")
    assert result.endswith(".wav")
