"""Diálogo que lista las actas generadas en el vault y permite abrirlas."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLabel,
)


def open_path(path: Path) -> None:
    if sys.platform == "win32":
        import os
        os.startfile(str(path))  # noqa: S606
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


def reveal_path(path: Path) -> None:
    """Abre el explorador mostrando/seleccionando el archivo o carpeta."""
    if sys.platform == "win32":
        if path.is_file():
            subprocess.Popen(["explorer", "/select,", str(path)])
        else:
            subprocess.Popen(["explorer", str(path)])
    elif sys.platform == "darwin":
        subprocess.Popen(["open", "-R", str(path)] if path.is_file() else ["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path.parent if path.is_file() else path)])


class ActasListWindow(QDialog):
    def __init__(self, actas_dir: Path, parent=None):
        super().__init__(parent)
        self.actas_dir = Path(actas_dir)
        self.setWindowTitle("Actas — Mis actas")
        self.setMinimumSize(560, 420)
        self._build()
        self._reload()

    def _build(self):
        self.info = QLabel("")
        self.list = QListWidget()
        self.list.itemDoubleClicked.connect(self._open_selected)

        open_btn = QPushButton("Abrir acta")
        open_btn.clicked.connect(self._open_selected)
        reveal_btn = QPushButton("Mostrar en carpeta")
        reveal_btn.clicked.connect(self._reveal_selected)
        folder_btn = QPushButton("Abrir carpeta de actas")
        folder_btn.clicked.connect(lambda: reveal_path(self.actas_dir))
        reload_btn = QPushButton("Actualizar")
        reload_btn.clicked.connect(self._reload)
        close_btn = QPushButton("Cerrar")
        close_btn.clicked.connect(self.accept)

        btns = QHBoxLayout()
        btns.addWidget(open_btn)
        btns.addWidget(reveal_btn)
        btns.addWidget(folder_btn)
        btns.addWidget(reload_btn)
        btns.addStretch(1)
        btns.addWidget(close_btn)

        root = QVBoxLayout()
        root.addWidget(self.info)
        root.addWidget(self.list, 1)
        root.addLayout(btns)
        self.setLayout(root)

    def _reload(self):
        self.list.clear()
        if not self.actas_dir.exists():
            self.info.setText(f"La carpeta de actas aún no existe: {self.actas_dir}")
            return
        actas = sorted(
            self.actas_dir.glob("Acta *.md"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not actas:
            self.info.setText(
                "Todavía no hay actas. Graba una reunión (Ctrl+Alt+R) y aparecerá aquí."
            )
            return
        self.info.setText(f"{len(actas)} acta(s) en {self.actas_dir}")
        for p in actas:
            item = QListWidgetItem(p.stem)
            item.setData(Qt.UserRole, str(p))
            self.list.addItem(item)
        self.list.setCurrentRow(0)

    def _selected_path(self) -> Path | None:
        item = self.list.currentItem()
        if not item:
            return None
        return Path(item.data(Qt.UserRole))

    def _open_selected(self):
        p = self._selected_path()
        if p and p.exists():
            open_path(p)

    def _reveal_selected(self):
        p = self._selected_path()
        if p and p.exists():
            reveal_path(p)
