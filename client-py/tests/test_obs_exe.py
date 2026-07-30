"""Resolucion del ejecutable de OBS (multiplataforma)."""
from __future__ import annotations

from pathlib import Path

import actas.infra as infra
from actas.config import Config


def test_usa_la_ruta_configurada_si_existe(tmp_path, monkeypatch):
    exe = tmp_path / "obs64.exe"
    exe.write_text("x")
    cfg = Config()
    cfg.obs_exe = str(exe)
    assert infra.resolve_obs_exe(cfg) == exe


def test_ruta_configurada_inexistente_devuelve_none():
    cfg = Config()
    cfg.obs_exe = r"Z:\no\existe\obs64.exe"
    assert infra.resolve_obs_exe(cfg) is None


def test_sin_configurar_busca_en_el_path(monkeypatch):
    monkeypatch.setattr(infra.shutil, "which", lambda n: "/usr/bin/obs" if n == "obs" else None)
    cfg = Config()
    cfg.obs_exe = ""
    assert infra.resolve_obs_exe(cfg) == Path("/usr/bin/obs")


def test_sin_configurar_y_sin_path_prueba_rutas_habituales(tmp_path, monkeypatch):
    candidato = tmp_path / "obs64.exe"
    candidato.write_text("x")
    monkeypatch.setattr(infra.shutil, "which", lambda n: None)
    monkeypatch.setattr(infra, "_OBS_CANDIDATES", {infra.sys.platform: [str(candidato)]})
    cfg = Config()
    cfg.obs_exe = ""
    assert infra.resolve_obs_exe(cfg) == candidato


def test_no_encontrado_devuelve_none(monkeypatch):
    monkeypatch.setattr(infra.shutil, "which", lambda n: None)
    monkeypatch.setattr(infra, "_OBS_CANDIDATES", {})
    cfg = Config()
    cfg.obs_exe = ""
    assert infra.resolve_obs_exe(cfg) is None


def test_default_de_config_no_cablea_windows():
    # Cablear una ruta de Windows dejaba el cliente inservible en otros sistemas.
    assert Config().obs_exe == ""
