from __future__ import annotations

import sys
import threading
import time
import traceback
from typing import Any

from PySide6.QtCore import QLockFile, QTimer, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QLabel, QMessageBox, QProgressBar, QSplashScreen

from sciplot.paths import APP_ICON_PNG, RUNTIME_DIR, startup_log_path
from sciplot.version import APP_NAME, APP_VERSION


class StartupSplash(QSplashScreen):
    def __init__(self, application: QApplication) -> None:
        canvas = QPixmap(460, 300)
        canvas.fill(QColor("#f8fafc"))
        painter = QPainter(canvas)
        try:
            if APP_ICON_PNG.exists():
                logo = QPixmap(str(APP_ICON_PNG)).scaled(
                    132,
                    132,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                painter.drawPixmap((canvas.width() - logo.width()) // 2, 30, logo)
            painter.setPen(QColor("#172033"))
            painter.setFont(QFont(application.font().family(), 19, QFont.Weight.Bold))
            painter.drawText(canvas.rect().adjusted(0, 174, 0, -88), Qt.AlignmentFlag.AlignHCenter, APP_NAME)
            painter.setPen(QColor("#607086"))
            painter.setFont(QFont(application.font().family(), 9))
            painter.drawText(canvas.rect().adjusted(0, 207, 0, -62), Qt.AlignmentFlag.AlignHCenter, f"Version {APP_VERSION}")
        finally:
            painter.end()

        super().__init__(canvas, Qt.WindowType.WindowStaysOnTopHint)
        self.setWindowTitle(f"{APP_NAME} - Starting")
        self.status_label = QLabel("Starting SciPlot...", self)
        self.status_label.setGeometry(30, 236, 400, 22)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("color: #526177; background: transparent;")
        self.progress = QProgressBar(self)
        self.progress.setGeometry(44, 268, 372, 7)
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.progress.setStyleSheet(
            "QProgressBar { border: 0; background: #dbe3ef; }"
            "QProgressBar::chunk { background: #2368e8; }"
        )

    def set_status(self, message: str) -> None:
        self.status_label.setText(message)

    def mousePressEvent(self, event: Any) -> None:  # noqa: N802
        event.ignore()


def _write_startup_error(details: str) -> str:
    try:
        path = startup_log_path()
        path.write_text(details, encoding="utf-8")
        return str(path)
    except Exception:
        return str(RUNTIME_DIR / "startup_error.log")


def _configure_early_application() -> QApplication:
    application = QApplication.instance() or QApplication(sys.argv)
    application.setApplicationName(APP_NAME)
    application.setApplicationVersion(APP_VERSION)
    application.setOrganizationName(APP_NAME)
    if APP_ICON_PNG.exists():
        application.setWindowIcon(QIcon(str(APP_ICON_PNG)))
    return application


def run_launcher(startup_smoke: bool = False) -> int:
    started = time.perf_counter()
    application = _configure_early_application()
    lock = QLockFile(str(RUNTIME_DIR / "sciplot.lock"))
    lock.setStaleLockTime(10_000)
    if not lock.tryLock(0):
        QMessageBox.information(None, APP_NAME, "SciPlot is already starting or running.")
        return 0

    splash = StartupSplash(application)
    splash.show()
    application.processEvents()
    state: dict[str, Any] = {}

    def import_application() -> None:
        try:
            from sciplot import app as app_module

            state["module"] = app_module
        except BaseException:
            state["error"] = traceback.format_exc()

    def fail_startup(details: str) -> None:
        log_path = _write_startup_error(details)
        splash.close()
        QMessageBox.critical(None, f"{APP_NAME} startup failed", f"SciPlot could not start.\n\nError log: {log_path}")
        application.exit(1)

    last_second = -1

    def poll_import() -> None:
        nonlocal last_second
        if "error" in state:
            fail_startup(str(state["error"]))
            return
        if "module" not in state:
            elapsed = int(time.perf_counter() - started)
            if elapsed != last_second:
                last_second = elapsed
                splash.set_status(f"Loading scientific libraries... {elapsed}s")
            QTimer.singleShot(80, poll_import)
            return

        try:
            splash.set_status("Preparing workspace...")
            application.processEvents()
            app_module = state["module"]
            app_module.create_application()
            window = app_module.MainWindow(
                restore_previous=not startup_smoke,
                allow_auto_update=not startup_smoke,
            )
            state["window"] = window
            window.show()
            splash.finish(window)
            if startup_smoke:
                QTimer.singleShot(200, lambda: (window.close(), application.quit()))
        except BaseException:
            fail_startup(traceback.format_exc())

    threading.Thread(target=import_application, name="SciPlotStartup", daemon=True).start()
    QTimer.singleShot(50, poll_import)
    exit_code = application.exec()
    lock.unlock()
    return exit_code


def main() -> int:
    if "--smoke-test" in sys.argv or "--gui-smoke" in sys.argv:
        from sciplot.app import guarded_main

        return guarded_main()
    return run_launcher(startup_smoke="--startup-smoke" in sys.argv)


def guarded_main() -> int:
    try:
        return main()
    except BaseException:
        details = traceback.format_exc()
        log_path = _write_startup_error(details)
        try:
            application = _configure_early_application()
            QMessageBox.critical(None, f"{APP_NAME} startup failed", f"SciPlot could not start.\n\nError log: {log_path}")
            application.processEvents()
        except Exception:
            print(details, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(guarded_main())
