"""Iconos generados en runtime (sin archivos externos): círculo de micrófono.

- idle: gris
- recording: rojo
- busy: ámbar
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap, QBrush


def _make(color: QColor, size: int = 64) -> QIcon:
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)

    # círculo de fondo
    p.setPen(Qt.NoPen)
    p.setBrush(QBrush(color))
    p.drawEllipse(2, 2, size - 4, size - 4)

    # icono de micrófono simple (cápsula + base) en blanco
    p.setBrush(QBrush(QColor("white")))
    cap_w = size * 0.26
    cap_h = size * 0.40
    cx = size / 2
    p.drawRoundedRect(
        QRectF(cx - cap_w / 2, size * 0.22, cap_w, cap_h), cap_w / 2, cap_w / 2
    )
    # base/soporte
    pen = p.pen()
    pen.setColor(QColor("white"))
    pen.setWidthF(size * 0.05)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    arc_r = size * 0.30
    p.drawArc(
        QRectF(cx - arc_r, size * 0.30, arc_r * 2, arc_r * 2), 200 * 16, 140 * 16
    )
    p.setPen(Qt.NoPen)
    p.setBrush(QBrush(QColor("white")))
    p.drawRect(QRectF(cx - size * 0.03, size * 0.62, size * 0.06, size * 0.12))
    p.drawRect(QRectF(cx - size * 0.12, size * 0.74, size * 0.24, size * 0.05))

    p.end()
    return QIcon(pm)


def idle_icon() -> QIcon:
    return _make(QColor(90, 96, 110))   # gris azulado


def recording_icon() -> QIcon:
    return _make(QColor(220, 50, 50))   # rojo


def busy_icon() -> QIcon:
    return _make(QColor(220, 160, 40))  # ámbar
