"""App de bandeja Actas (PySide6).

Grabar y procesar están DESACOPLADOS:
- Grabar usa OBS y es inmediato (icono rojo). Al detener, el trabajo se ENCOLA y
  vuelves a poder grabar al instante.
- Una cola en background (1 a la vez) sube cada grabación al servidor y escribe la
  nota. Los fallos se reintentan solos cuando el servidor vuelve.

Icono: gris (idle), rojo (grabando), ámbar (procesando en background).
"""
from __future__ import annotations

import sys

from PySide6.QtCore import QObject, QThread, Signal, Qt
from PySide6.QtWidgets import (
    QApplication, QSystemTrayIcon, QMenu, QInputDialog, QMessageBox,
)

from .config import Config
from .recorder import Recorder, RecorderError
from .queue_worker import ProcessingQueue, Counts
from .settings_window import SettingsWindow
from .hotkey import GlobalHotkey
from . import icons


class RecordWorker(QObject):
    """Inicia o detiene la grabación de OBS en un hilo aparte (no bloquea la UI).

    'stop' devuelve la ruta del .mka para encolarlo; 'start' solo arranca OBS.
    """
    started_ok = Signal()
    stopped_ok = Signal(str)           # ruta del archivo grabado
    failed = Signal(str)               # error

    def __init__(self, recorder: Recorder, action: str):
        super().__init__()
        self.recorder = recorder
        self.action = action

    def run(self):
        try:
            if self.action == "start":
                self.recorder.start()
                self.started_ok.emit()
            else:
                path = self.recorder.stop()
                self.stopped_ok.emit(str(path))
        except RecorderError as e:
            self.failed.emit(str(e))
        except Exception as e:  # pragma: no cover
            self.failed.emit(f"Error inesperado: {e}")


class ActasTray(QObject):
    def __init__(self, app: QApplication):
        super().__init__()
        self.app = app
        self.cfg = Config.load()
        self.recorder = Recorder(self.cfg)
        self._rec_thread: QThread | None = None
        self._rec_worker: RecordWorker | None = None
        self._busy_recording_op = False   # arrancando/deteniendo OBS
        self._counts = Counts()

        # Cola de procesamiento en background
        self.queue = ProcessingQueue(self.cfg)
        self.queue.job_started.connect(self._on_job_started)
        self.queue.job_done.connect(self._on_job_done)
        self.queue.job_failed.connect(self._on_job_failed)
        self.queue.queue_changed.connect(self._on_queue_changed)
        self.queue.progress.connect(self._on_queue_progress)
        self.queue.start()

        self.tray = QSystemTrayIcon(icons.idle_icon())
        self.tray.activated.connect(self._on_tray_activated)
        self._build_menu()
        self.tray.show()
        self._update_visual()

        self.hotkey = GlobalHotkey(self.app, self.toggle)
        hk = self.hotkey.register()
        hint = "Ctrl+Alt+R o clic en el icono" if hk else "Clic en el icono"
        self._notify("Estela", f"Listo. {hint} para grabar.")

    # --- menú ---

    def _build_menu(self):
        menu = QMenu()
        self.act_toggle = menu.addAction("Iniciar grabación")
        self.act_toggle.triggered.connect(self.toggle)
        menu.addSeparator()
        self.act_status = menu.addAction("Sin trabajos en cola")
        self.act_status.setEnabled(False)
        self.act_retry = menu.addAction("Reintentar fallidos")
        self.act_retry.triggered.connect(self.queue.retry_failed)
        menu.addSeparator()
        act_actas = menu.addAction("Ver mis actas…")
        act_actas.triggered.connect(self._open_actas_list)
        act_vault = menu.addAction("Abrir carpeta de actas")
        act_vault.triggered.connect(self._open_vault)
        act_settings = menu.addAction("Ajustes…")
        act_settings.triggered.connect(self._open_settings)
        menu.addSeparator()
        act_quit = menu.addAction("Salir")
        act_quit.triggered.connect(self._quit)
        self.tray.setContextMenu(menu)

    # --- grabación (desacoplada del procesamiento) ---

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            self.toggle()

    def toggle(self):
        if self._busy_recording_op:
            return  # ya arrancando/deteniendo OBS (operación breve)
        if self.recorder.recording:
            self._stop()
        else:
            self._start()

    def _start(self):
        self._busy_recording_op = True
        self._run_record_worker("start")

    def _stop(self):
        # Pedir título ANTES de detener (rápido) para encolar con nombre
        title = self.cfg.default_title
        if self.cfg.ask_title:
            text, ok = QInputDialog.getText(
                None, "Estela", "Título de la reunión:", text=self.cfg.default_title
            )
            if not ok:
                return  # cancelado: sigue grabando
            title = text.strip() or self.cfg.default_title
        self._pending_title = title
        self._busy_recording_op = True
        self._run_record_worker("stop")

    def _run_record_worker(self, action: str):
        self._rec_thread = QThread()
        self._rec_worker = RecordWorker(self.recorder, action)
        self._rec_worker.moveToThread(self._rec_thread)
        self._rec_thread.started.connect(self._rec_worker.run)
        self._rec_worker.started_ok.connect(self._on_record_started)
        self._rec_worker.stopped_ok.connect(self._on_record_stopped)
        self._rec_worker.failed.connect(self._on_record_failed)
        self._rec_thread.start()

    def _cleanup_rec_thread(self):
        if self._rec_thread:
            self._rec_thread.quit()
            self._rec_thread.wait()
        self._rec_thread = None
        self._rec_worker = None
        self._busy_recording_op = False

    def _on_record_started(self):
        self._cleanup_rec_thread()
        self._update_visual()
        self._notify("Estela", "Grabación iniciada.")

    def _on_record_stopped(self, path: str):
        self._cleanup_rec_thread()
        # Encolar para procesar en background -> la app queda libre para grabar otra
        self.queue.enqueue(path, getattr(self, "_pending_title", self.cfg.default_title))
        self._update_visual()
        self._notify("Estela", "Grabación encolada para procesar. Puedes grabar otra.")

    def _on_record_failed(self, error: str):
        self._cleanup_rec_thread()
        self._update_visual()
        self._notify("Estela — error", error, error=True)

    # --- señales de la cola ---

    def _on_job_started(self, title: str):
        self._update_visual()

    def _on_job_done(self, title: str, note_name: str):
        self._notify("Acta lista", note_name)
        self._update_visual()

    def _on_job_failed(self, title: str, error: str):
        self._notify("Estela — error (se reintentará)", f"{title}: {error}", error=True)
        self._update_visual()

    def _on_queue_changed(self, queued: int, processing: int, failed: int):
        self._counts = Counts(queued=queued, processing=processing, failed=failed)
        self._update_visual()

    def _on_queue_progress(self, detail: str):
        self._update_tooltip(detail)

    # --- estado visual ---

    def _update_visual(self):
        rec = self.recorder.recording
        c = self._counts
        if rec:
            self.tray.setIcon(icons.recording_icon())
        elif c.active > 0:
            self.tray.setIcon(icons.busy_icon())
        else:
            self.tray.setIcon(icons.idle_icon())
        # menú
        self.act_toggle.setText("Detener y procesar" if rec else "Iniciar grabación")
        parts = []
        if c.processing:
            parts.append(f"{c.processing} procesando")
        if c.queued:
            parts.append(f"{c.queued} en cola")
        if c.failed:
            parts.append(f"{c.failed} fallidos")
        self.act_status.setText("· ".join(parts) if parts else "Sin trabajos en cola")
        self.act_retry.setEnabled(c.failed > 0)
        self.act_retry.setText(
            f"Reintentar fallidos ({c.failed})" if c.failed else "Reintentar fallidos"
        )
        self._update_tooltip()

    def _update_tooltip(self, detail: str = ""):
        rec = self.recorder.recording
        c = self._counts
        if rec:
            base = "GRABANDO"
        elif c.active:
            base = "Procesando"
        else:
            base = "Inactivo"
        extra = []
        if c.active:
            extra.append(f"{c.active} en cola")
        if c.failed:
            extra.append(f"{c.failed} fallidos")
        tip = f"Estela — {base}"
        if extra:
            tip += " · " + " · ".join(extra)
        if detail:
            tip += f" — {detail}"
        self.tray.setToolTip(tip)

    # --- otras acciones ---

    def _open_actas_list(self):
        from .actas_list import ActasListWindow
        self._actas_win = ActasListWindow(self.cfg.actas_path())
        self._actas_win.exec()

    def _open_vault(self):
        from .actas_list import reveal_path
        reveal_path(self.cfg.actas_path())

    def _open_settings(self):
        from .log import get_logger
        try:
            self._settings_win = SettingsWindow(self.cfg)
            self._settings_win.exec()
            self.recorder.cfg = self.cfg
            self.queue.cfg = self.cfg
            self._update_visual()
        except Exception:
            get_logger().exception("error abriendo/cerrando Ajustes")

    def _quit(self):
        if self.recorder.recording:
            r = QMessageBox.question(
                None, "Estela", "Hay una grabación en curso. ¿Salir igualmente?"
            )
            if r != QMessageBox.Yes:
                return
        if self._counts.active:
            r = QMessageBox.question(
                None, "Estela",
                f"Hay {self._counts.active} trabajo(s) en cola sin terminar. "
                "Quedarán guardados y se procesarán al reabrir. ¿Salir?",
            )
            if r != QMessageBox.Yes:
                return
        self.hotkey.unregister()
        self.queue.shutdown()
        self.tray.hide()
        self.app.quit()

    # --- helpers ---

    def _notify(self, title: str, msg: str, error: bool = False):
        icon = QSystemTrayIcon.Critical if error else QSystemTrayIcon.Information
        self.tray.showMessage(title, msg, icon, 5000)


def _acquire_single_instance():
    """Evita 2 instancias (pelearían por la misma cola). Devuelve el lock o None."""
    from PySide6.QtNetwork import QLocalServer, QLocalSocket
    name = "estela-single-instance"
    sock = QLocalSocket()
    sock.connectToServer(name)
    if sock.waitForConnected(200):
        sock.disconnectFromServer()
        return None  # ya hay una instancia
    QLocalServer.removeServer(name)  # limpiar restos de un cierre sucio
    server = QLocalServer()
    server.listen(name)
    return server


def _install_excepthook():
    """Loguea cualquier excepción no capturada (en vez de cerrar la app en silencio)."""
    from .log import get_logger
    from PySide6.QtCore import qInstallMessageHandler, QtMsgType
    log = get_logger()

    def hook(exc_type, exc, tb):
        log.error("EXCEPCION NO CAPTURADA", exc_info=(exc_type, exc, tb))
    sys.excepthook = hook

    # Capturar también los mensajes nativos de Qt (warnings/críticos/fatales)
    def qt_handler(mode, ctx, message):
        if mode in (QtMsgType.QtCriticalMsg, QtMsgType.QtFatalMsg):
            log.error("QT: %s", message)
        elif mode == QtMsgType.QtWarningMsg:
            log.warning("QT: %s", message)
    qInstallMessageHandler(qt_handler)


def main():
    _install_excepthook()
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    lock = _acquire_single_instance()
    if lock is None:
        QMessageBox.information(
            None, "Estela", "Estela ya está en ejecución (mira la bandeja del sistema)."
        )
        return 0

    if not QSystemTrayIcon.isSystemTrayAvailable():
        QMessageBox.critical(None, "Estela", "No hay bandeja del sistema disponible.")
        return 1
    tray = ActasTray(app)  # noqa: F841
    app._actas_lock = lock  # mantener vivo el lock
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

