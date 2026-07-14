"""Infraestructura: OBS process, salud del servidor, encendido de la VM (Proxmox),
arranque del servidor local y resolución del servidor efectivo (cascada NAS -> local)."""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable, Optional

import httpx

from .config import Config
from .log import get_logger


log = get_logger()


def _no_window_kwargs() -> dict:
    """Evita ventanas de consola en Windows al lanzar procesos."""
    if sys.platform == "win32":
        return {"creationflags": subprocess.CREATE_NO_WINDOW}
    return {}


def tcp_open(host: str, port: int, timeout: float = 0.4) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def obs_running() -> bool:
    if sys.platform == "win32":
        out = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq obs64.exe", "/NH"],
            capture_output=True, text=True, **_no_window_kwargs(),
        )
        return "obs64.exe" in out.stdout
    out = subprocess.run(["pgrep", "-x", "obs"], capture_output=True, text=True)
    return out.returncode == 0


def ensure_obs(cfg: Config, wait_s: int = 20) -> bool:
    """Arranca OBS oculto si no corre y espera a que el WebSocket responda."""
    port = int(cfg.obs_url.rsplit(":", 1)[-1])
    if not tcp_open("127.0.0.1", port):
        if not obs_running():
            exe = Path(cfg.obs_exe)
            if not exe.exists():
                raise FileNotFoundError(f"No se encontró OBS en {exe}")
            subprocess.Popen(
                [str(exe), "--minimize-to-tray", "--disable-shutdown-check"],
                cwd=str(exe.parent),
                **_no_window_kwargs(),
            )
        for _ in range(wait_s * 2):
            if tcp_open("127.0.0.1", port):
                break
            time.sleep(0.5)
    return tcp_open("127.0.0.1", port)


def url_healthy(base_url: str, timeout: float = 4.0) -> bool:
    """True si <base_url>/health responde 200 con status ok."""
    if not base_url:
        return False
    try:
        r = httpx.get(f"{base_url}/health", timeout=timeout)
        return r.status_code == 200 and r.json().get("status") == "ok"
    except Exception:
        return False


def server_healthy(cfg: Config, timeout: float = 4.0) -> bool:
    return url_healthy(cfg.server_url, timeout=timeout)


def ollama_up(base_url: str, timeout: float = 3.0) -> bool:
    """True si Ollama responde en <base_url>/api/tags."""
    try:
        r = httpx.get(f"{base_url}/api/tags", timeout=timeout)
        return r.status_code == 200
    except Exception:
        return False


def start_vm(cfg: Config) -> tuple[bool, str]:
    """Enciende la VM por SSH al host Proxmox. Devuelve (ok, mensaje)."""
    try:
        proc = subprocess.run(
            ["ssh", "-o", "ConnectTimeout=8", f"root@{cfg.proxmox_host}",
             f"qm start {cfg.vm_id}"],
            capture_output=True, text=True, timeout=30, **_no_window_kwargs(),
        )
        if proc.returncode == 0:
            return True, "VM encendida"
        return False, (proc.stderr or proc.stdout or "error ssh").strip()
    except Exception as e:
        return False, str(e)


def wait_server(cfg: Config, wait_s: int = 200) -> bool:
    """Espera a que el server primario responda (tras encender la VM)."""
    deadline = time.time() + wait_s
    while time.time() < deadline:
        if server_healthy(cfg, timeout=4):
            return True
        time.sleep(5)
    return False


def _wait_url(base_url: str, wait_s: int, interval: float = 3.0,
              health: Callable[[str], bool] = url_healthy) -> bool:
    deadline = time.time() + wait_s
    while time.time() < deadline:
        if health(base_url):
            return True
        time.sleep(interval)
    return False


def _local_server_paths(cfg: Config) -> tuple[Path, Path]:
    """Resuelve (directorio del server local, python del venv)."""
    server_dir = Path(cfg.local_server_dir) if cfg.local_server_dir else Path()
    if cfg.local_server_python:
        py = Path(cfg.local_server_python)
    else:
        py = server_dir / ".venv" / (
            "Scripts/python.exe" if sys.platform == "win32" else "bin/python"
        )
    return server_dir, py


def _load_env_file(env_path: Path) -> dict:
    """Lee las variables ACTAS_* de un archivo .env (el server no auto-carga .env)."""
    env: dict[str, str] = {}
    if not env_path.exists():
        return env
    for line in env_path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        k = k.strip()
        if k.startswith("ACTAS_"):
            env[k] = v.strip()
    return env


def start_local_server(cfg: Config) -> tuple[bool, str]:
    """Arranca Ollama (si no responde) y el actas-server local con su .env.

    Devuelve (ok, mensaje). ok=True cuando local_server_url/health responde.
    """
    server_dir, py = _local_server_paths(cfg)
    if not server_dir or not server_dir.exists():
        return False, f"local_server_dir no válido: {server_dir}"
    if not py.exists():
        return False, f"python del venv local no encontrado: {py}"

    # 1) Ollama: arrancar si no responde
    if not ollama_up(cfg.local_ollama_url):
        try:
            subprocess.Popen(["ollama", "serve"], **_no_window_kwargs())
        except FileNotFoundError:
            return False, "Ollama no está instalado (comando 'ollama' no encontrado)."
        if not _wait_url(cfg.local_ollama_url, wait_s=30,
                         health=lambda u: ollama_up(u)):
            return False, "Ollama no respondió tras arrancar."

    # 2) actas-server local: arrancar si no responde
    if not url_healthy(cfg.local_server_url):
        env = os.environ.copy()
        env.update(_load_env_file(server_dir / ".env"))
        host, port = _host_port(cfg.local_server_url)
        try:
            subprocess.Popen(
                [str(py), "-m", "uvicorn", "app.main:app",
                 "--host", host, "--port", str(port)],
                cwd=str(server_dir), env=env, **_no_window_kwargs(),
            )
        except Exception as e:  # noqa: BLE001
            return False, f"No se pudo lanzar el server local: {e}"
        # Primer arranque descarga/carga modelos: dar margen amplio
        if not _wait_url(cfg.local_server_url, wait_s=240):
            return False, "El server local no quedó listo a tiempo."

    return True, "Servidor local disponible"


def _host_port(base_url: str) -> tuple[str, int]:
    """Extrae host y puerto de una URL http(s)://host:port."""
    rest = base_url.split("://", 1)[-1].split("/", 1)[0]
    if ":" in rest:
        host, port = rest.rsplit(":", 1)
        return host or "127.0.0.1", int(port)
    return rest or "127.0.0.1", 80


def resolve_server(cfg: Config, emit: Optional[Callable[[str, str], None]] = None
                   ) -> Optional[str]:
    """Devuelve la URL del servidor efectivo a usar, o None si ninguno está disponible.

    Cascada:
      1. primario (server_url) healthy -> primario.
      2. auto_start_vm: encender VM + esperar -> primario.
      3. local (local_server_url) healthy -> local.
      4. auto_start_local: arrancar local -> local.
    """
    say = emit or (lambda s, d: None)

    # 1) Primario ya disponible
    if url_healthy(cfg.server_url):
        return cfg.server_url

    # 2) Intentar encender la VM del primario
    if cfg.auto_start_vm and cfg.proxmox_host and cfg.vm_id:
        say("vm", "Servidor principal apagado, encendiéndolo…")
        ok, msg = start_vm(cfg)
        log.info("start_vm -> ok=%s msg=%s", ok, msg)
        if ok and wait_server(cfg):
            return cfg.server_url
        log.warning("no se pudo usar el servidor principal: %s", msg)

    # 3) Local ya disponible
    if url_healthy(cfg.local_server_url):
        say("local", "Usando servidor local")
        return cfg.local_server_url

    # 4) Arrancar el servidor local
    if cfg.auto_start_local:
        say("local", "Arrancando servidor local (Ollama + actas-server)…")
        ok, msg = start_local_server(cfg)
        log.info("start_local_server -> ok=%s msg=%s", ok, msg)
        if ok:
            return cfg.local_server_url
        log.warning("no se pudo arrancar el servidor local: %s", msg)

    return None
