"""Infraestructura: OBS process, salud del servidor, encendido de la VM (Proxmox)."""
from __future__ import annotations

import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx

from .config import Config


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


def server_healthy(cfg: Config, timeout: float = 4.0) -> bool:
    try:
        r = httpx.get(f"{cfg.server_url}/health", timeout=timeout)
        return r.status_code == 200 and r.json().get("status") == "ok"
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
    """Espera a que el server responda (tras encender la VM)."""
    deadline = time.time() + wait_s
    while time.time() < deadline:
        if server_healthy(cfg, timeout=4):
            return True
        time.sleep(5)
    return False
