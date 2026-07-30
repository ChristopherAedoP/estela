"""Tests de la cascada de resolución de servidor (NAS -> VM -> local -> arranque local)."""
from __future__ import annotations

import pytest

import actas.infra as infra
from actas.config import Config

# Referencia a la implementacion real, porque el fixture autouse de abajo la
# sustituye para el resto de tests.
_SERVER_READY_REAL = infra.server_ready


@pytest.fixture(autouse=True)
def _servidor_operativo(monkeypatch):
    """Por defecto, todo servidor que responde tambien puede transcribir.

    Los tests que prueban lo contrario lo sobreescriben.
    """
    monkeypatch.setattr(infra, "server_ready", lambda url, timeout=180.0: (True, "ok"))


def _cfg(**overrides) -> Config:
    cfg = Config()
    cfg.server_url = "http://nas:8770"
    cfg.local_server_url = "http://localhost:8770"
    cfg.auto_start_vm = False
    cfg.auto_start_local = False
    for k, v in overrides.items():
        setattr(cfg, k, v)
    return cfg


def test_primario_disponible_usa_primario(monkeypatch):
    monkeypatch.setattr(infra, "url_healthy", lambda url, timeout=4.0: url == "http://nas:8770")
    assert infra.resolve_server(_cfg()) == "http://nas:8770"


def test_primario_caido_local_disponible_usa_local(monkeypatch):
    monkeypatch.setattr(
        infra, "url_healthy", lambda url, timeout=4.0: url == "http://localhost:8770"
    )
    assert infra.resolve_server(_cfg()) == "http://localhost:8770"


def test_ambos_caidos_sin_autostart_devuelve_none(monkeypatch):
    monkeypatch.setattr(infra, "url_healthy", lambda url, timeout=4.0: False)
    assert infra.resolve_server(_cfg()) is None


def test_primario_caido_arranca_local_ok(monkeypatch):
    # Ni primario ni local responden inicialmente; el arranque local tiene éxito.
    monkeypatch.setattr(infra, "url_healthy", lambda url, timeout=4.0: False)
    called = {}

    def fake_start_local(cfg):
        called["start"] = True
        return True, "ok"

    monkeypatch.setattr(infra, "start_local_server", fake_start_local)
    cfg = _cfg(auto_start_local=True)
    assert infra.resolve_server(cfg) == "http://localhost:8770"
    assert called.get("start") is True


def test_primario_caido_arranca_local_falla_devuelve_none(monkeypatch):
    monkeypatch.setattr(infra, "url_healthy", lambda url, timeout=4.0: False)
    monkeypatch.setattr(infra, "start_local_server", lambda cfg: (False, "sin ollama"))
    assert infra.resolve_server(_cfg(auto_start_local=True)) is None


def test_vm_arranca_y_primario_queda_healthy(monkeypatch):
    # Primario inicialmente caído; tras start_vm + wait_server queda healthy.
    monkeypatch.setattr(infra, "url_healthy", lambda url, timeout=4.0: False)
    monkeypatch.setattr(infra, "start_vm", lambda cfg: (True, "VM encendida"))
    monkeypatch.setattr(infra, "wait_server", lambda cfg, wait_s=200: True)
    cfg = _cfg(auto_start_vm=True, proxmox_host="proxmox-host.example", vm_id="120")
    assert infra.resolve_server(cfg) == "http://nas:8770"


def test_vm_falla_cae_a_local(monkeypatch):
    # start_vm falla; el local sí responde -> se usa el local.
    monkeypatch.setattr(
        infra, "url_healthy", lambda url, timeout=4.0: url == "http://localhost:8770"
    )
    monkeypatch.setattr(infra, "start_vm", lambda cfg: (False, "ssh timeout"))
    cfg = _cfg(auto_start_vm=True, proxmox_host="proxmox-host.example", vm_id="120")
    assert infra.resolve_server(cfg) == "http://localhost:8770"


def test_primario_responde_pero_no_puede_transcribir_cae_a_local(monkeypatch):
    # El caso que dejaba la cola en bucle: /health decia "ok" y cada trabajo
    # terminaba en 500 porque la pila de modelos del servidor estaba rota.
    monkeypatch.setattr(infra, "url_healthy", lambda url, timeout=4.0: True)
    monkeypatch.setattr(
        infra,
        "server_ready",
        lambda url, timeout=180.0: (False, "torch roto") if url == "http://nas:8770" else (True, "ok"),
    )
    assert infra.resolve_server(_cfg()) == "http://localhost:8770"


def test_ninguno_puede_transcribir_devuelve_none(monkeypatch):
    monkeypatch.setattr(infra, "url_healthy", lambda url, timeout=4.0: True)
    monkeypatch.setattr(infra, "server_ready", lambda url, timeout=180.0: (False, "degraded"))
    assert infra.resolve_server(_cfg()) is None


def test_server_ready_acepta_servidor_antiguo_sin_deep(monkeypatch):
    # Un servidor previo ignora el parametro deep y responde el ok de siempre.
    class _R:
        status_code = 200

        @staticmethod
        def json():
            return {"status": "ok"}

    monkeypatch.setattr(infra.httpx, "get", lambda *a, **kw: _R())
    ok, detalle = _SERVER_READY_REAL("http://viejo:8770")
    assert ok is True
    assert detalle == "ok"


def test_server_ready_detecta_degradado(monkeypatch):
    class _R:
        status_code = 200

        @staticmethod
        def json():
            return {"status": "degraded", "checks": {"pipeline": {"torch": False}}}

    monkeypatch.setattr(infra.httpx, "get", lambda *a, **kw: _R())
    ok, detalle = _SERVER_READY_REAL("http://roto:8770")
    assert ok is False
    assert "torch" in detalle


def test_host_port_parsing():
    assert infra._host_port("http://127.0.0.1:8770") == ("127.0.0.1", 8770)
    assert infra._host_port("http://localhost:11434") == ("localhost", 11434)
