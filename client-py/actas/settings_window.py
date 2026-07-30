"""Ventana de ajustes del cliente Actas."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QDialog, QFormLayout, QLineEdit, QComboBox, QCheckBox,
    QPushButton, QHBoxLayout, QVBoxLayout, QLabel, QMessageBox, QWidget,
    QFileDialog, QDoubleSpinBox,
)

from .config import Config
from .obs_client import ObsClient
from . import infra


class SettingsWindow(QDialog):
    def __init__(self, cfg: Config, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.setWindowTitle("Actas — Ajustes")
        self.setMinimumWidth(520)
        self._build()

    def _build(self):
        form = QFormLayout()

        self.device_combo = QComboBox()
        self.device_combo.addItem(self.cfg.audio_device_label or "Por defecto",
                                  self.cfg.audio_device_id or "default")
        refresh_btn = QPushButton("Detectar salidas")
        refresh_btn.clicked.connect(self._refresh_devices)
        dev_row = QHBoxLayout()
        dev_row.addWidget(self.device_combo, 1)
        dev_row.addWidget(refresh_btn)
        dev_widget = QWidget(); dev_widget.setLayout(dev_row)
        form.addRow("Salida a grabar:", dev_widget)

        self.gain_spin = QDoubleSpinBox()
        self.gain_spin.setRange(0.0, 30.0)
        self.gain_spin.setSingleStep(2.0)
        self.gain_spin.setSuffix(" dB")
        self.gain_spin.setValue(self.cfg.audio_gain_db)
        self.gain_spin.setToolTip(
            "Ganancia de captura. Sube a 20 dB si grabas la salida HDMI de un "
            "monitor (se captura muy bajo). 0 dB = sin ganancia."
        )
        form.addRow("Ganancia de audio:", self.gain_spin)

        self.server_edit = QLineEdit(self.cfg.server_url)
        self.server_edit.setToolTip("Servidor principal (p. ej. el del NAS).")
        form.addRow("Servidor:", self.server_edit)

        self.local_server_edit = QLineEdit(self.cfg.local_server_url)
        self.local_server_edit.setToolTip(
            "Servidor local de respaldo. Se usa si el principal no responde."
        )
        form.addRow("Servidor local:", self.local_server_edit)

        self.auto_local_chk = QCheckBox(
            "Arrancar el servidor local automáticamente si el principal no responde"
        )
        self.auto_local_chk.setChecked(self.cfg.auto_start_local)
        form.addRow("", self.auto_local_chk)

        self.local_dir_edit = QLineEdit(self.cfg.local_server_dir)
        self.local_dir_edit.setPlaceholderText(
            "Ej: ruta a la carpeta server/ del repo (contiene .venv y .env)"
        )
        local_dir_browse = QPushButton("Examinar…")
        local_dir_browse.clicked.connect(self._browse_local_dir)
        local_dir_row = QHBoxLayout()
        local_dir_row.addWidget(self.local_dir_edit, 1)
        local_dir_row.addWidget(local_dir_browse)
        local_dir_widget = QWidget(); local_dir_widget.setLayout(local_dir_row)
        form.addRow("Carpeta server local:", local_dir_widget)

        self.vault_edit = QLineEdit(self.cfg.vault_path)
        vault_browse = QPushButton("Examinar…")
        vault_browse.clicked.connect(self._browse_vault)
        vault_row = QHBoxLayout()
        vault_row.addWidget(self.vault_edit, 1)
        vault_row.addWidget(vault_browse)
        vault_widget = QWidget(); vault_widget.setLayout(vault_row)
        form.addRow("Vault Obsidian:", vault_widget)

        self.actas_edit = QLineEdit(self.cfg.actas_dir)
        self.actas_edit.setPlaceholderText("Ej: Actas  (relativa al vault) o una ruta absoluta")
        actas_browse = QPushButton("Examinar…")
        actas_browse.clicked.connect(self._browse_actas)
        actas_row = QHBoxLayout()
        actas_row.addWidget(self.actas_edit, 1)
        actas_row.addWidget(actas_browse)
        actas_widget = QWidget(); actas_widget.setLayout(actas_row)
        form.addRow("Carpeta de actas:", actas_widget)

        self.proxmox_edit = QLineEdit(self.cfg.proxmox_host)
        form.addRow("Host Proxmox:", self.proxmox_edit)

        self.vm_edit = QLineEdit(self.cfg.vm_id)
        form.addRow("VM ID:", self.vm_edit)

        self.title_edit = QLineEdit(self.cfg.default_title)
        form.addRow("Título por defecto:", self.title_edit)

        self.ask_title_chk = QCheckBox("Preguntar título antes de grabar")
        self.ask_title_chk.setChecked(self.cfg.ask_title)
        form.addRow("", self.ask_title_chk)

        self.auto_vm_chk = QCheckBox("Encender la VM automáticamente al grabar")
        self.auto_vm_chk.setChecked(self.cfg.auto_start_vm)
        form.addRow("", self.auto_vm_chk)

        self.delete_local_chk = QCheckBox(
            "Borrar la grabación local tras subirla (el audio queda en el NAS)"
        )
        self.delete_local_chk.setChecked(self.cfg.delete_local_after_upload)
        form.addRow("", self.delete_local_chk)

        self.status_lbl = QLabel("")
        self.status_lbl.setWordWrap(True)

        save_btn = QPushButton("Guardar")
        save_btn.clicked.connect(self._save)
        test_btn = QPushButton("Probar servidor")
        test_btn.clicked.connect(self._test_server)
        cancel_btn = QPushButton("Cerrar")
        cancel_btn.clicked.connect(self.reject)

        btns = QHBoxLayout()
        btns.addWidget(test_btn)
        btns.addStretch(1)
        btns.addWidget(save_btn)
        btns.addWidget(cancel_btn)

        root = QVBoxLayout()
        root.addLayout(form)
        root.addWidget(self.status_lbl)
        root.addLayout(btns)
        self.setLayout(root)

    def _refresh_devices(self):
        from .log import get_logger
        log = get_logger()
        self.status_lbl.setText("Iniciando OBS y detectando salidas…")
        QApplication.processEvents()
        try:
            if not infra.ensure_obs(self.cfg):
                self.status_lbl.setText("OBS no respondió (puerto 4455). ¿Está instalado?")
                log.error("ensure_obs devolvió False")
                return
            with ObsClient(self.cfg.obs_url, self.cfg.obs_password) as obs:
                if not obs.input_exists(self.cfg.obs_input_name):
                    self.status_lbl.setText(
                        f"OBS no tiene la fuente '{self.cfg.obs_input_name}'. "
                        "Falta la escena Actas (reinstala la config de OBS)."
                    )
                    log.error("fuente inexistente: %s", self.cfg.obs_input_name)
                    return
                devices = obs.list_output_devices(self.cfg.obs_input_name)
            log.info("dispositivos detectados: %d", len(devices))
            current = self.device_combo.currentData()
            self.device_combo.clear()
            for d in devices:
                self.device_combo.addItem(d["label"], d["id"])
            idx = self.device_combo.findData(current)
            if idx >= 0:
                self.device_combo.setCurrentIndex(idx)
            if len(devices) <= 1:
                self.status_lbl.setText(
                    "Solo se detectó 'Por defecto'. Pulsa de nuevo 'Detectar salidas' "
                    "(OBS puede tardar en enumerar el audio tras arrancar)."
                )
            else:
                self.status_lbl.setText(f"{len(devices)} salidas detectadas.")
        except Exception as e:
            log.exception("error detectando salidas")
            self.status_lbl.setText(f"Error detectando salidas: {e}")

    def _browse_local_dir(self):
        start = self.local_dir_edit.text() or str(Path.home())
        d = QFileDialog.getExistingDirectory(
            self, "Elegir carpeta del server local", start
        )
        if d:
            self.local_dir_edit.setText(d)

    def _browse_vault(self):
        d = QFileDialog.getExistingDirectory(
            self, "Elegir carpeta del vault", self.vault_edit.text() or str(Path.home())
        )
        if d:
            self.vault_edit.setText(d)

    def _browse_actas(self):
        start = self.vault_edit.text() or str(Path.home())
        d = QFileDialog.getExistingDirectory(self, "Elegir carpeta de actas", start)
        if d:
            # si está dentro del vault, guardar como relativa (más portable)
            try:
                rel = Path(d).relative_to(Path(self.vault_edit.text()))
                self.actas_edit.setText(str(rel))
            except (ValueError, Exception):
                self.actas_edit.setText(d)

    def _test_server(self):
        primary = self.server_edit.text().strip()
        local = self.local_server_edit.text().strip()
        if infra.url_healthy(primary):
            self.status_lbl.setText("Servidor principal OK")
        elif infra.url_healthy(local):
            self.status_lbl.setText(
                "El principal no responde; el servidor local SÍ responde."
            )
        else:
            self.status_lbl.setText(
                "Ni el principal ni el local responden. "
                "Con arranque automático, el local se levantará al grabar."
            )

    def _save(self):
        from .log import get_logger
        log = get_logger()
        try:
            self.cfg.server_url = self.server_edit.text().strip()
            self.cfg.local_server_url = self.local_server_edit.text().strip()
            self.cfg.auto_start_local = self.auto_local_chk.isChecked()
            self.cfg.local_server_dir = self.local_dir_edit.text().strip()
            self.cfg.vault_path = self.vault_edit.text().strip()
            self.cfg.actas_dir = self.actas_edit.text().strip()
            self.cfg.proxmox_host = self.proxmox_edit.text().strip()
            self.cfg.vm_id = self.vm_edit.text().strip()
            self.cfg.default_title = self.title_edit.text().strip() or "Reunión"
            self.cfg.ask_title = self.ask_title_chk.isChecked()
            self.cfg.auto_start_vm = self.auto_vm_chk.isChecked()
            self.cfg.delete_local_after_upload = self.delete_local_chk.isChecked()
            self.cfg.audio_device_id = self.device_combo.currentData() or "default"
            self.cfg.audio_device_label = self.device_combo.currentText()
            self.cfg.audio_gain_db = self.gain_spin.value()
            self.cfg.save()
            log.info("ajustes guardados")
        except Exception as e:
            log.exception("error al guardar ajustes")
            self.status_lbl.setText(f"Error al guardar: {e}")
            return
        self.accept()
