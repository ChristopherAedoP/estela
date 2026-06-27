"""Hotkey global multiplataforma (best-effort).

En Windows usa RegisterHotKey vía un event filter nativo de Qt (sin dependencias).
En otras plataformas no registra nada (se puede ampliar con pynput si se desea).
"""
from __future__ import annotations

import sys
from typing import Callable

from PySide6.QtCore import QAbstractNativeEventFilter, QObject

# Modificadores y VK para Windows
_MOD_ALT = 0x0001
_MOD_CONTROL = 0x0002
_WM_HOTKEY = 0x0312
_HOTKEY_ID = 0xA17A  # arbitrario


class _WinHotkeyFilter(QAbstractNativeEventFilter):
    def __init__(self, callback: Callable[[], None]):
        super().__init__()
        self._cb = callback

    def nativeEventFilter(self, event_type, message):
        if event_type == b"windows_generic_MSG":
            import ctypes
            msg = ctypes.wintypes.MSG.from_address(int(message))
            if msg.message == _WM_HOTKEY and msg.wParam == _HOTKEY_ID:
                self._cb()
        return False, 0


class GlobalHotkey(QObject):
    """Registra Ctrl+Alt+R global. Llama a `callback` cuando se pulsa."""

    def __init__(self, app, callback: Callable[[], None]):
        super().__init__()
        self._app = app
        self._cb = callback
        self._filter = None
        self._registered = False

    def register(self, vk: int = 0x52) -> bool:  # 0x52 = 'R'
        if sys.platform != "win32":
            return False
        try:
            import ctypes
            import ctypes.wintypes  # noqa: F401 (carga wintypes)
            user32 = ctypes.windll.user32
            ok = user32.RegisterHotKey(None, _HOTKEY_ID, _MOD_CONTROL | _MOD_ALT, vk)
            if not ok:
                return False
            self._filter = _WinHotkeyFilter(self._cb)
            self._app.installNativeEventFilter(self._filter)
            self._registered = True
            return True
        except Exception:
            return False

    def unregister(self):
        if self._registered and sys.platform == "win32":
            try:
                import ctypes
                ctypes.windll.user32.UnregisterHotKey(None, _HOTKEY_ID)
            except Exception:
                pass
            self._registered = False
