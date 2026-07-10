from __future__ import annotations

import os
import sys
import traceback

from PySide6.QtGui import QColor, QFont, QIcon, QPalette
from PySide6.QtWidgets import QApplication

from .data_io import read_data_file
from .main_window import MainWindow
from .models import PlotSettings
from .paths import APP_ICON_PNG, EXPORT_DIR, SAMPLE_DIR, startup_log_path
from .plotting import save_figure
from .project_io import dataframe_from_json, dataframe_to_json
from .version import APP_NAME, APP_VERSION


STYLE_SHEET = """
QMainWindow, QWidget { background: #f4f7fb; color: #172033; }
QMenuBar { background: #ffffff; border-bottom: 1px solid #dbe3ef; padding: 2px; }
QMenuBar::item { padding: 6px 10px; background: transparent; }
QMenuBar::item:selected, QMenu::item:selected { background: #e8f0ff; color: #174fbf; }
QMenu { background: #ffffff; border: 1px solid #d4deec; padding: 5px; }
QMenu::item { padding: 7px 28px 7px 10px; }
QToolBar { background: #ffffff; border: 0; border-bottom: 1px solid #dbe3ef; padding: 7px; spacing: 5px; }
QToolButton { background: transparent; border: 1px solid transparent; border-radius: 4px; padding: 6px 9px; }
QToolButton:hover { background: #edf3ff; border-color: #c7d8f5; }
QToolButton:checked { background: #dbe9ff; border-color: #8eb4f5; color: #174fbf; }
QDockWidget { color: #172033; font-weight: 600; }
QDockWidget::title { background: #edf2f8; border: 1px solid #d9e2ef; padding: 8px; }
QTabWidget::pane { background: #ffffff; border: 1px solid #d8e1ed; }
QTabBar::tab { background: #eaf0f7; border: 1px solid #d8e1ed; padding: 8px 14px; min-width: 68px; }
QTabBar::tab:selected { background: #ffffff; color: #1f66f2; border-bottom-color: #ffffff; }
QScrollArea, QTableView { background: #ffffff; border: 0; }
QLabel { background: transparent; }
QLabel#SectionTitle { font-size: 15px; font-weight: 700; }
QLabel#EmptyTitle { font-size: 23px; font-weight: 700; color: #15233b; padding-top: 10px; }
QLabel#MutedText { color: #607086; }
QLabel#WarningText { color: #8a4b08; background: #fff7e6; border: 1px solid #f2cd8c; padding: 8px; border-radius: 4px; }
QPushButton { background: #ffffff; border: 1px solid #b9c6d8; border-radius: 4px; padding: 7px 12px; min-height: 20px; }
QPushButton:hover { background: #f3f7fd; border-color: #7da6e8; }
QPushButton:pressed { background: #e5eefc; }
QPushButton#PrimaryButton { background: #2368e8; color: #ffffff; border-color: #2368e8; font-weight: 600; }
QPushButton#PrimaryButton:hover { background: #174fbf; }
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QListWidget { background: #ffffff; border: 1px solid #bfcbdc; border-radius: 3px; padding: 5px 7px; selection-background-color: #246bfe; }
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QListWidget:focus { border: 1px solid #3478ed; }
QComboBox::drop-down { border: 0; width: 24px; }
QListWidget::item { padding: 4px; }
QListWidget::item:selected { background: #246bfe; color: #ffffff; }
QCheckBox { spacing: 8px; padding: 3px 0; }
QHeaderView::section { background: #eaf0f7; color: #25344d; border: 0; border-right: 1px solid #d5deea; border-bottom: 1px solid #d5deea; padding: 7px; font-weight: 600; }
QTableView { gridline-color: #e3e9f1; alternate-background-color: #f8fafc; selection-background-color: #dbe9ff; selection-color: #172033; }
QStatusBar { background: #ffffff; border-top: 1px solid #dbe3ef; color: #526177; }
QProgressBar { border: 1px solid #bfcbdc; border-radius: 3px; background: #eef2f7; text-align: center; }
QProgressBar::chunk { background: #2368e8; }
"""


def create_application() -> QApplication:
    application = QApplication.instance() or QApplication(sys.argv)
    application.setApplicationName(APP_NAME)
    application.setApplicationVersion(APP_VERSION)
    application.setOrganizationName(APP_NAME)
    application.setStyle("Fusion")
    application.setFont(QFont("Segoe UI" if sys.platform.startswith("win") else ".AppleSystemUIFont" if sys.platform == "darwin" else "Noto Sans", 10))
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#f4f7fb"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#172033"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#f8fafc"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#172033"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#172033"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#246bfe"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    application.setPalette(palette)
    application.setStyleSheet(STYLE_SHEET)
    if APP_ICON_PNG.exists():
        application.setWindowIcon(QIcon(str(APP_ICON_PNG)))
    return application


def run_application() -> int:
    application = create_application()
    window = MainWindow()
    window.show()
    return application.exec()


def run_smoke_test() -> None:
    import pandas as pd

    sample_path = SAMPLE_DIR / "example_measurements.csv"
    dataframe = read_data_file(sample_path)
    settings = PlotSettings(chart_type="line", x_col="time_s", y_cols=["signal_a", "signal_b"], group_col="group", title="SciPlot 3 smoke test")
    for suffix in ("png", "svg", "pdf"):
        output = EXPORT_DIR / f"smoke_test.{suffix}"
        save_figure(dataframe, settings, str(output), 150)
        if not output.exists() or output.stat().st_size < 1000:
            raise RuntimeError(f"{suffix.upper()} smoke export failed")
        print(output)
    density_output = EXPORT_DIR / "density_smoke.png"
    density_settings = PlotSettings(chart_type="density", y_cols=["signal_a"], title="SciPlot density smoke test")
    save_figure(dataframe, density_settings, str(density_output), 150)
    if not density_output.exists() or density_output.stat().st_size < 1000:
        raise RuntimeError("Packaged SciPy density smoke test failed")
    print(density_output)
    colorbar_output = EXPORT_DIR / "colorbar_smoke.svg"
    colorbar_settings = PlotSettings(
        chart_type="scatter3d",
        x_col="time_s",
        y_cols=["signal_a"],
        z_col="temperature_c",
        title="SciPlot 3D colorbar smoke test",
    )
    save_figure(dataframe, colorbar_settings, str(colorbar_output), 150)
    if not colorbar_output.exists() or colorbar_output.stat().st_size < 1000:
        raise RuntimeError("Packaged 3D colorbar smoke test failed")
    print(colorbar_output)
    date_frame = pd.DataFrame({"when": [pd.Timestamp("2026-01-01")], "value": [1.5]})
    restored = dataframe_from_json(dataframe_to_json(date_frame))
    if not pd.api.types.is_datetime64_any_dtype(restored["when"]):
        raise RuntimeError("Datetime project serialization failed")


def run_gui_smoke_test() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    application = create_application()
    window = MainWindow(restore_previous=False, allow_auto_update=False)
    dataframe = read_data_file(SAMPLE_DIR / "example_measurements.csv")
    settings = PlotSettings(chart_type="line", x_col="time_s", y_cols=["signal_a"], group_col="group", title="GUI smoke")
    window._apply_dataframe(dataframe, "example_measurements.csv", settings=settings, render=True)
    application.processEvents()
    if window.figure is None or window.canvas is None:
        raise RuntimeError("Qt GUI smoke test did not render a figure")
    output = EXPORT_DIR / "gui_smoke.svg"
    save_figure(dataframe, settings, str(output), 150)
    if not output.exists() or output.stat().st_size < 1000:
        raise RuntimeError("Qt GUI export smoke test failed")
    colorbar_settings = PlotSettings(
        chart_type="scatter3d",
        x_col="time_s",
        y_cols=["signal_a"],
        z_col="temperature_c",
        title="GUI colorbar smoke",
    )
    window.apply_settings(colorbar_settings, render=True)
    application.processEvents()
    if window.figure is None or "colorbar" not in getattr(window.figure, "_sciplot_artists", {}):
        raise RuntimeError("Qt GUI smoke test did not register the 3D colorbar")
    window._apply_dataframe(dataframe.copy(), "new_measurements.csv")
    application.processEvents()
    if window.figure is not None or window.last_rendered_settings is not None or window.preview_stack.currentIndex() != 0:
        raise RuntimeError("Importing new data left the previous figure visible")
    window.close()
    application.processEvents()
    print("gui-ok")


def main() -> int:
    if "--smoke-test" in sys.argv:
        run_smoke_test()
        return 0
    if "--gui-smoke" in sys.argv:
        run_gui_smoke_test()
        return 0
    return run_application()


def guarded_main() -> int:
    try:
        return main()
    except BaseException:
        details = traceback.format_exc()
        try:
            path = startup_log_path()
            path.write_text(details, encoding="utf-8")
            print(f"SciPlot startup failed. Log: {path}", file=sys.stderr)
        except Exception:
            print(details, file=sys.stderr)
        return 1
