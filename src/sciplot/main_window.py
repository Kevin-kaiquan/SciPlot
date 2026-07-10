from __future__ import annotations

import json
import re
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

import pandas as pd
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from PySide6.QtCore import QItemSelectionModel, QSettings, QThreadPool, QTimer, Qt, QUrl
from PySide6.QtGui import QAction, QActionGroup, QCloseEvent, QDesktopServices, QDragEnterEvent, QDropEvent, QIcon, QKeySequence, QPixmap, QResizeEvent, QShowEvent, QUndoCommand, QUndoStack
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDockWidget,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QStyle,
    QTabWidget,
    QTableView,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from .data_io import numeric_columns, read_data_file, suggest_columns
from .drag import LabelDragController
from .i18n import LANGUAGES, tr
from .models import CHART_DEFINITIONS, PALETTES, PlotSettings, chart_label
from .paths import APP_DATA_ROOT, APP_ICON_PNG, EXPORT_DIR, PROJECT_DIR, SAMPLE_DIR, SESSION_PATH, TEMPLATE_DIR, UPDATE_DIR
from .plotting import PlotEngine, chart_requirements, save_figure
from .project_io import ProjectData, SessionSourceChangedError, load_project, load_session, save_project, save_session
from .table_model import PandasTableModel
from .updater import UpdateInfo, download_update, fetch_latest_release
from .version import APP_NAME, APP_VERSION
from .workers import FunctionWorker


DATA_FIELDS = {"chart_type", "x_col", "y_cols", "z_col", "error_col", "group_col", "size_col", "color_col", "title", "xlabel", "ylabel", "zlabel"}


class SettingsCommand(QUndoCommand):
    def __init__(self, window: "MainWindow", before: PlotSettings, after: PlotSettings, text: str, skip_first_redo: bool = False) -> None:
        super().__init__(text)
        self.window = window
        self.before = before
        self.after = after
        self.skip_first_redo = skip_first_redo
        self.first_redo = True

    def undo(self) -> None:
        self.window.apply_settings(self.before, render=True)

    def redo(self) -> None:
        if self.first_redo and self.skip_first_redo:
            self.first_redo = False
            self.window.current_settings = self.after
            return
        self.first_redo = False
        self.window.apply_settings(self.after, render=True)


class ExportDialog(QDialog):
    def __init__(self, parent: QWidget, language: str, suggested_name: str, dpi: int) -> None:
        super().__init__(parent)
        self.language = language
        self.setWindowTitle(tr("export", language))
        self.setMinimumWidth(560)
        layout = QFormLayout(self)
        self.path_edit = QLineEdit(str(EXPORT_DIR / f"{suggested_name}.png"))
        browse = QPushButton("...")
        browse.setFixedWidth(42)
        browse.clicked.connect(self._browse)
        path_row = QWidget()
        path_layout = QHBoxLayout(path_row)
        path_layout.setContentsMargins(0, 0, 0, 0)
        path_layout.addWidget(self.path_edit)
        path_layout.addWidget(browse)
        layout.addRow(tr("export", language), path_row)
        self.dpi_spin = QSpinBox()
        self.dpi_spin.setRange(72, 1200)
        self.dpi_spin.setValue(dpi)
        layout.addRow(tr("dpi", language), self.dpi_spin)
        self.transparent = QCheckBox("Transparent background" if language == "en" else ("透明背景" if language == "zh_TW" else "透明背景"))
        layout.addRow("", self.transparent)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def _browse(self) -> None:
        path, selected_filter = QFileDialog.getSaveFileName(
            self,
            tr("export", self.language),
            self.path_edit.text(),
            "PNG (*.png);;SVG (*.svg);;PDF (*.pdf)",
        )
        if path:
            if not Path(path).suffix:
                extension = ".svg" if "SVG" in selected_filter else ".pdf" if "PDF" in selected_filter else ".png"
                path += extension
            self.path_edit.setText(path)

    def values(self) -> tuple[Path, int, bool]:
        return Path(self.path_edit.text()).expanduser(), self.dpi_spin.value(), self.transparent.isChecked()


class MainWindow(QMainWindow):
    def __init__(self, restore_previous: bool = True, allow_auto_update: bool = True) -> None:
        super().__init__()
        self.dataframe = pd.DataFrame()
        self.data_source = ""
        self.current_settings = PlotSettings()
        self.last_rendered_settings: PlotSettings | None = None
        self.engine = PlotEngine(self.dataframe)
        self.figure: Figure | None = None
        self.canvas: FigureCanvasQTAgg | None = None
        self.drag_controller: LabelDragController | None = None
        self.thread_pool = QThreadPool.globalInstance()
        self.session_thread_pool = QThreadPool(self)
        self.session_thread_pool.setMaxThreadCount(1)
        self._workers: set[FunctionWorker] = set()
        self._applying_settings = False
        self._busy_count = 0
        self._right_auto_hidden = False
        self.settings_store = QSettings(str(APP_DATA_ROOT / "settings.ini"), QSettings.Format.IniFormat)
        self.language = str(self.settings_store.value("language", "en"))
        if self.language not in LANGUAGES:
            self.language = "en"
        self.undo_stack = QUndoStack(self)
        self.actions: dict[str, QAction] = {}
        self.menus: dict[str, QMenu] = {}
        self.form_labels: dict[str, list[QLabel]] = {}
        self.plot_rows: dict[str, tuple[QLabel, QWidget]] = {}
        self.style_rows: dict[str, tuple[QLabel, QWidget]] = {}

        self.setWindowTitle(f"{APP_NAME} {APP_VERSION}")
        self.setMinimumSize(900, 600)
        self.resize(1360, 860)
        self.setAcceptDrops(True)
        if APP_ICON_PNG.exists():
            self.setWindowIcon(QIcon(str(APP_ICON_PNG)))

        self._build_actions()
        self._build_menu()
        self._build_toolbar()
        self._build_central_workspace()
        self._build_docks()
        self._build_status_bar()
        self._connect_undo_actions()
        self._update_action_states()
        self.retranslate_ui()
        self._restore_window_state()

        if restore_previous:
            QTimer.singleShot(100, self.restore_last_session)
        if allow_auto_update and self.auto_update_action.isChecked():
            QTimer.singleShot(4000, self._auto_check_updates)

    def _standard_icon(self, pixmap: QStyle.StandardPixmap) -> QIcon:
        return self.style().standardIcon(pixmap)

    def _action(self, key: str, callback: Any, shortcut: str | QKeySequence | None = None, icon: QIcon | None = None, checkable: bool = False) -> QAction:
        action = QAction(icon or QIcon(), "", self)
        action.setCheckable(checkable)
        if shortcut:
            action.setShortcut(QKeySequence(shortcut) if isinstance(shortcut, str) else shortcut)
        action.triggered.connect(callback)
        self.actions[key] = action
        return action

    def _build_actions(self) -> None:
        self._action("new", self.new_workspace, QKeySequence.StandardKey.New, self._standard_icon(QStyle.StandardPixmap.SP_FileIcon))
        self._action("open_data", self.import_data, QKeySequence.StandardKey.Open, self._standard_icon(QStyle.StandardPixmap.SP_DialogOpenButton))
        self._action("sample_data", self.load_sample_data, "Ctrl+Shift+O", self._standard_icon(QStyle.StandardPixmap.SP_DirOpenIcon))
        self._action("open_project", self.open_project, "Ctrl+Alt+O", self._standard_icon(QStyle.StandardPixmap.SP_DialogOpenButton))
        self._action("save_project", self.save_project, QKeySequence.StandardKey.Save, self._standard_icon(QStyle.StandardPixmap.SP_DialogSaveButton))
        self._action("export", self.export_figure, "Ctrl+E", self._standard_icon(QStyle.StandardPixmap.SP_DialogSaveButton))
        self._action("generate", self.generate_figure, "Ctrl+Return", self._standard_icon(QStyle.StandardPixmap.SP_MediaPlay))
        self._action("move_labels", self.toggle_label_dragging, "Ctrl+L", self._standard_icon(QStyle.StandardPixmap.SP_TitleBarNormalButton), checkable=True)
        self._action("reset_labels", self.reset_label_positions)
        self._action("check_updates", lambda: self.check_for_updates(silent=False), icon=self._standard_icon(QStyle.StandardPixmap.SP_BrowserReload))
        self.auto_update_action = self._action("auto_updates", self._set_auto_updates, checkable=True)
        auto_value = str(self.settings_store.value("auto_updates", "true")).lower() not in {"false", "0", "no"}
        self.auto_update_action.setChecked(auto_value)
        self._action("about", self.show_about, icon=self._standard_icon(QStyle.StandardPixmap.SP_MessageBoxInformation))
        self._action("quit", self.close, QKeySequence.StandardKey.Quit)

    def _build_menu(self) -> None:
        self.menus["file"] = self.menuBar().addMenu("")
        for key in ("new", "open_data", "sample_data", "open_project", "save_project", "export"):
            self.menus["file"].addAction(self.actions[key])
        self.menus["file"].addSeparator()
        self.menus["file"].addAction(self.actions["quit"])

        self.menus["edit"] = self.menuBar().addMenu("")
        self.undo_action = self.undo_stack.createUndoAction(self)
        self.redo_action = self.undo_stack.createRedoAction(self)
        self.undo_action.setIcon(self._standard_icon(QStyle.StandardPixmap.SP_ArrowBack))
        self.redo_action.setIcon(self._standard_icon(QStyle.StandardPixmap.SP_ArrowForward))
        self.undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        self.redo_action.setShortcut(QKeySequence.StandardKey.Redo)
        self.menus["edit"].addAction(self.undo_action)
        self.menus["edit"].addAction(self.redo_action)
        self.menus["edit"].addSeparator()
        self.menus["edit"].addAction(self.actions["move_labels"])
        self.menus["edit"].addAction(self.actions["reset_labels"])

        self.menus["view"] = self.menuBar().addMenu("")
        self.menus["tools"] = self.menuBar().addMenu("")
        self.menus["tools"].addAction(self.actions["generate"])
        self.menus["tools"].addAction(self.actions["check_updates"])
        self.menus["tools"].addAction(self.actions["auto_updates"])

        self.menus["language"] = self.menuBar().addMenu("")
        group = QActionGroup(self)
        group.setExclusive(True)
        for code, label in LANGUAGES.items():
            action = QAction(label, self, checkable=True)
            action.setData(code)
            action.setChecked(code == self.language)
            action.triggered.connect(lambda checked=False, value=code: self.set_language(value))
            group.addAction(action)
            self.menus["language"].addAction(action)

        self.menus["help"] = self.menuBar().addMenu("")
        self.menus["help"].addAction(self.actions["about"])

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("Main", self)
        self.main_toolbar = toolbar
        toolbar.setObjectName("MainToolbar")
        toolbar.setMovable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.addToolBar(toolbar)
        if APP_ICON_PNG.exists():
            logo = QLabel()
            pixmap = QPixmap(str(APP_ICON_PNG)).scaled(32, 32, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            logo.setPixmap(pixmap)
            logo.setContentsMargins(4, 0, 8, 0)
            toolbar.addWidget(logo)
        brand = QLabel(f"<b>{APP_NAME}</b> <span style='color:#64748b'>v{APP_VERSION}</span>")
        brand.setContentsMargins(0, 0, 14, 0)
        toolbar.addWidget(brand)
        toolbar.addSeparator()
        for key in ("open_data", "sample_data", "generate", "save_project", "export"):
            toolbar.addAction(self.actions[key])
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        spacer.setStyleSheet("background: transparent;")
        toolbar.addWidget(spacer)
        toolbar.addAction(self.undo_action)
        toolbar.addAction(self.redo_action)
        toolbar.addAction(self.actions["move_labels"])

    def _build_central_workspace(self) -> None:
        self.workspace_tabs = QTabWidget()
        self.setCentralWidget(self.workspace_tabs)

        self.preview_stack = QStackedWidget()
        empty_page = QWidget()
        empty_layout = QVBoxLayout(empty_page)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_logo = QLabel()
        if APP_ICON_PNG.exists():
            self.empty_logo.setPixmap(QPixmap(str(APP_ICON_PNG)).scaled(100, 100, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        self.empty_logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_title = QLabel()
        self.empty_title.setObjectName("EmptyTitle")
        self.empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_text = QLabel()
        self.empty_text.setObjectName("MutedText")
        self.empty_text.setWordWrap(True)
        self.empty_text.setMaximumWidth(520)
        self.empty_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_button = QPushButton()
        self.empty_button.setObjectName("PrimaryButton")
        self.empty_button.clicked.connect(self.import_data)
        self.empty_button.setMaximumWidth(220)
        for widget in (self.empty_logo, self.empty_title, self.empty_text, self.empty_button):
            empty_layout.addWidget(widget, 0, Qt.AlignmentFlag.AlignCenter)

        self.figure_page = QWidget()
        self.figure_layout = QVBoxLayout(self.figure_page)
        self.figure_layout.setContentsMargins(0, 0, 0, 0)
        self.preview_stack.addWidget(empty_page)
        self.preview_stack.addWidget(self.figure_page)
        self.workspace_tabs.addTab(self.preview_stack, "")

        self.table_model = PandasTableModel()
        self.data_table = QTableView()
        self.data_table.setModel(self.table_model)
        self.data_table.setAlternatingRowColors(True)
        self.data_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.data_table.setSortingEnabled(False)
        self.data_table.horizontalHeader().setStretchLastSection(False)
        self.workspace_tabs.addTab(self.data_table, "")

    def _scroll_page(self) -> tuple[QScrollArea, QWidget, QVBoxLayout]:
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QFrame.Shape.NoFrame)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        area.setWidget(content)
        return area, content, layout

    def _form_page(self) -> tuple[QScrollArea, QWidget, QFormLayout]:
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QFrame.Shape.NoFrame)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        form = QFormLayout(content)
        form.setContentsMargins(12, 12, 12, 12)
        form.setSpacing(10)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        area.setWidget(content)
        return area, content, form

    def _add_row(self, form: QFormLayout, key: str, widget: QWidget, target: dict[str, tuple[QLabel, QWidget]] | None = None) -> QLabel:
        label = QLabel()
        label.setWordWrap(True)
        form.addRow(label, widget)
        self.form_labels.setdefault(key, []).append(label)
        if target is not None:
            target[key] = (label, widget)
        return label

    def _combo(self, values: list[tuple[str, Any]] | None = None) -> QComboBox:
        combo = QComboBox()
        if values:
            for label, value in values:
                combo.addItem(label, value)
        return combo

    def _double_spin(self, minimum: float, maximum: float, value: float, step: float = 0.1, decimals: int = 2) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(minimum, maximum)
        spin.setDecimals(decimals)
        spin.setSingleStep(step)
        spin.setValue(value)
        return spin

    def _spin(self, minimum: int, maximum: int, value: int, step: int = 1) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(minimum, maximum)
        spin.setSingleStep(step)
        spin.setValue(value)
        return spin

    def _build_docks(self) -> None:
        self.left_dock = QDockWidget(self)
        self.left_dock.setObjectName("DataPlotDock")
        self.left_dock.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        self.left_dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable | QDockWidget.DockWidgetFeature.DockWidgetClosable | QDockWidget.DockWidgetFeature.DockWidgetFloatable)
        self.left_tabs = QTabWidget()
        self.left_dock.setWidget(self.left_tabs)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.left_dock)
        self.resizeDocks([self.left_dock], [290], Qt.Orientation.Horizontal)
        self._build_data_panel()
        self._build_plot_panel()

        self.right_dock = QDockWidget(self)
        self.right_dock.setObjectName("StyleLayoutDock")
        self.right_dock.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        self.right_dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable | QDockWidget.DockWidgetFeature.DockWidgetClosable | QDockWidget.DockWidgetFeature.DockWidgetFloatable)
        self.right_tabs = QTabWidget()
        self.right_dock.setWidget(self.right_tabs)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.right_dock)
        self.resizeDocks([self.right_dock], [300], Qt.Orientation.Horizontal)
        self._build_style_panel()
        self._build_layout_panel()
        self._build_template_panel()

        self.menus["view"].addAction(self.left_dock.toggleViewAction())
        self.menus["view"].addAction(self.right_dock.toggleViewAction())

    def _build_data_panel(self) -> None:
        area, _content, layout = self._scroll_page()
        self.source_title = QLabel()
        self.source_title.setObjectName("SectionTitle")
        self.source_label = QLabel()
        self.source_label.setObjectName("MutedText")
        self.source_label.setWordWrap(True)
        self.stats_label = QLabel("0 rows · 0 columns")
        self.data_warning = QLabel()
        self.data_warning.setObjectName("WarningText")
        self.data_warning.setWordWrap(True)
        self.data_warning.hide()
        self.import_button = QPushButton()
        self.import_button.setObjectName("PrimaryButton")
        self.import_button.clicked.connect(self.import_data)
        self.sample_button = QPushButton()
        self.sample_button.clicked.connect(self.load_sample_data)
        layout.addWidget(self.source_title)
        layout.addWidget(self.source_label)
        layout.addWidget(self.stats_label)
        layout.addWidget(self.data_warning)
        layout.addSpacing(8)
        layout.addWidget(self.import_button)
        layout.addWidget(self.sample_button)
        layout.addStretch(1)
        self.left_tabs.addTab(area, "")

    def _build_plot_panel(self) -> None:
        area, _content, form = self._form_page()
        self.chart_combo = QComboBox()
        self.chart_combo.currentIndexChanged.connect(self._update_chart_controls)
        self._add_row(form, "chart_type", self.chart_combo, self.plot_rows)
        self.x_combo = QComboBox()
        self._add_row(form, "x_column", self.x_combo, self.plot_rows)
        self.y_list = QListWidget()
        self.y_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.y_list.setMinimumHeight(130)
        self._add_row(form, "y_columns", self.y_list, self.plot_rows)
        self.error_combo = QComboBox()
        self._add_row(form, "error_column", self.error_combo, self.plot_rows)
        self.z_combo = QComboBox()
        self._add_row(form, "z_column", self.z_combo, self.plot_rows)
        self.size_combo = QComboBox()
        self._add_row(form, "size_column", self.size_combo, self.plot_rows)
        self.color_combo = QComboBox()
        self._add_row(form, "color_column", self.color_combo, self.plot_rows)
        self.group_combo = QComboBox()
        self._add_row(form, "group_column", self.group_combo, self.plot_rows)
        self.title_edit = QLineEdit()
        self._add_row(form, "title", self.title_edit, self.plot_rows)
        self.xlabel_edit = QLineEdit()
        self._add_row(form, "xlabel", self.xlabel_edit, self.plot_rows)
        self.ylabel_edit = QLineEdit()
        self._add_row(form, "ylabel", self.ylabel_edit, self.plot_rows)
        self.zlabel_edit = QLineEdit()
        self._add_row(form, "zlabel", self.zlabel_edit, self.plot_rows)
        self.generate_button = QPushButton()
        self.generate_button.setObjectName("PrimaryButton")
        self.generate_button.clicked.connect(self.generate_figure)
        form.addRow(self.generate_button)
        self.left_tabs.addTab(area, "")

    def _build_style_panel(self) -> None:
        area, _content, form = self._form_page()
        self.width_spin = self._double_spin(2, 16, 7.2, 0.1, 1)
        self._add_row(form, "width", self.width_spin, self.style_rows)
        self.height_spin = self._double_spin(2, 12, 4.2, 0.1, 1)
        self._add_row(form, "height", self.height_spin, self.style_rows)
        self.dpi_spin = self._spin(72, 1200, 300, 10)
        self._add_row(form, "dpi", self.dpi_spin, self.style_rows)
        self.font_spin = self._spin(6, 28, 10)
        self._add_row(form, "font_size", self.font_spin, self.style_rows)
        self.line_width_spin = self._double_spin(0.2, 8, 1.8, 0.1, 1)
        self._add_row(form, "line_width", self.line_width_spin, self.style_rows)
        self.marker_size_spin = self._double_spin(0, 18, 5, 0.5, 1)
        self._add_row(form, "marker_size", self.marker_size_spin, self.style_rows)
        self.marker_combo = self._combo([("○", "o"), ("□", "s"), ("△", "^"), ("◇", "D"), ("×", "x"), ("+", "+"), ("·", "."), ("None", "")])
        self._add_row(form, "marker", self.marker_combo, self.style_rows)
        self.palette_combo = self._combo([(name, name) for name in PALETTES])
        self._add_row(form, "palette", self.palette_combo, self.style_rows)
        self.bins_spin = self._spin(5, 120, 30)
        self._add_row(form, "bins", self.bins_spin, self.style_rows)
        self.elev_spin = self._spin(-90, 90, 28)
        self._add_row(form, "elevation", self.elev_spin, self.style_rows)
        self.azim_spin = self._spin(-180, 180, -55)
        self._add_row(form, "azimuth", self.azim_spin, self.style_rows)
        self.x_scale_combo = self._combo([("Linear", "linear"), ("Log", "log"), ("SymLog", "symlog")])
        self._add_row(form, "x_scale", self.x_scale_combo, self.style_rows)
        self.y_scale_combo = self._combo([("Linear", "linear"), ("Log", "log"), ("SymLog", "symlog")])
        self._add_row(form, "y_scale", self.y_scale_combo, self.style_rows)
        self.missing_combo = self._combo([("Drop incomplete rows", "drop"), ("Interpolate", "interpolate"), ("Treat as zero", "zero")])
        self._add_row(form, "missing_policy", self.missing_combo, self.style_rows)
        self.grid_check = QCheckBox()
        self.grid_check.setChecked(True)
        form.addRow(self.grid_check)
        self.legend_check = QCheckBox()
        self.legend_check.setChecked(True)
        form.addRow(self.legend_check)
        self.tight_check = QCheckBox()
        self.tight_check.setChecked(True)
        form.addRow(self.tight_check)
        self.sort_check = QCheckBox()
        self.sort_check.setChecked(True)
        form.addRow(self.sort_check)
        self.polar_degrees_check = QCheckBox("Degrees")
        self.polar_degrees_check.setChecked(True)
        form.addRow(self.polar_degrees_check)
        self.radar_normalize_check = QCheckBox("Normalize radar axes")
        self.radar_normalize_check.setChecked(True)
        form.addRow(self.radar_normalize_check)
        self.right_tabs.addTab(area, "")

    def _build_layout_panel(self) -> None:
        area, _content, form = self._form_page()
        self.title_pad_spin = self._spin(0, 80, 14)
        self._add_row(form, "title_pad", self.title_pad_spin)
        self.axis_pad_spin = self._spin(0, 60, 8)
        self._add_row(form, "axis_pad", self.axis_pad_spin)
        self.tick_pad_spin = self._spin(0, 40, 4)
        self._add_row(form, "tick_pad", self.tick_pad_spin)
        self.rotation_spin = self._spin(-90, 90, 0)
        self._add_row(form, "tick_rotation", self.rotation_spin)
        self.legend_position_combo = self._combo([("Auto", "auto"), ("Upper right", "upper_right"), ("Upper left", "upper_left"), ("Right", "right"), ("Bottom", "bottom"), ("None", "none")])
        self._add_row(form, "legend_position", self.legend_position_combo)
        self.left_margin_spin = self._double_spin(0, 0.45, 0, 0.01, 2)
        self._add_row(form, "left_margin", self.left_margin_spin)
        self.right_margin_spin = self._double_spin(0, 0.45, 0, 0.01, 2)
        self._add_row(form, "right_margin", self.right_margin_spin)
        self.top_margin_spin = self._double_spin(0, 0.45, 0, 0.01, 2)
        self._add_row(form, "top_margin", self.top_margin_spin)
        self.bottom_margin_spin = self._double_spin(0, 0.45, 0, 0.01, 2)
        self._add_row(form, "bottom_margin", self.bottom_margin_spin)
        self.move_labels_button = QPushButton()
        self.move_labels_button.setCheckable(True)
        self.move_labels_button.toggled.connect(self.actions["move_labels"].setChecked)
        self.actions["move_labels"].toggled.connect(self.move_labels_button.setChecked)
        self.reset_labels_button = QPushButton()
        self.reset_labels_button.clicked.connect(self.reset_label_positions)
        form.addRow(self.move_labels_button)
        form.addRow(self.reset_labels_button)
        self.right_tabs.addTab(area, "")

    def _build_template_panel(self) -> None:
        area, _content, layout = self._scroll_page()
        self.template_combo = QComboBox()
        self.apply_template_button = QPushButton()
        self.apply_template_button.setObjectName("PrimaryButton")
        self.apply_template_button.clicked.connect(self.apply_template)
        self.save_template_button = QPushButton()
        self.save_template_button.clicked.connect(self.save_template)
        self.import_template_button = QPushButton()
        self.import_template_button.clicked.connect(self.import_template)
        self.export_template_button = QPushButton()
        self.export_template_button.clicked.connect(self.export_template)
        layout.addWidget(self.template_combo)
        layout.addWidget(self.apply_template_button)
        layout.addSpacing(8)
        layout.addWidget(self.save_template_button)
        layout.addWidget(self.import_template_button)
        layout.addWidget(self.export_template_button)
        layout.addStretch(1)
        self.right_tabs.addTab(area, "")
        self.refresh_templates()

    def _build_status_bar(self) -> None:
        self.status_label = QLabel()
        self.statusBar().addWidget(self.status_label, 1)
        self.progress = QProgressBar()
        self.progress.setFixedWidth(190)
        self.progress.hide()
        self.statusBar().addPermanentWidget(self.progress)

    def _connect_undo_actions(self) -> None:
        self.undo_stack.canUndoChanged.connect(self.undo_action.setEnabled)
        self.undo_stack.canRedoChanged.connect(self.redo_action.setEnabled)

    def _update_action_states(self) -> None:
        has_data = not self.dataframe.empty
        has_figure = has_data and self.figure is not None
        self.actions["generate"].setEnabled(has_data)
        self.actions["save_project"].setEnabled(has_data)
        self.actions["export"].setEnabled(has_figure)
        self.actions["move_labels"].setEnabled(has_figure)
        self.actions["reset_labels"].setEnabled(has_figure)
        self.generate_button.setEnabled(has_data)
        self.move_labels_button.setEnabled(has_figure)
        self.reset_labels_button.setEnabled(has_figure)

    def retranslate_ui(self) -> None:
        for key, action in self.actions.items():
            action.setText(tr(key, self.language))
            action.setToolTip(tr(key, self.language))
        self.undo_action.setText(tr("undo", self.language))
        self.redo_action.setText(tr("redo", self.language))
        for key, menu in self.menus.items():
            menu.setTitle(tr(key, self.language))
        self.left_dock.setWindowTitle(f"{tr('data', self.language)} / {tr('plot', self.language)}")
        self.right_dock.setWindowTitle(f"{tr('style', self.language)} / {tr('layout', self.language)}")
        self.left_tabs.setTabText(0, tr("data", self.language))
        self.left_tabs.setTabText(1, tr("plot", self.language))
        self.right_tabs.setTabText(0, tr("style", self.language))
        self.right_tabs.setTabText(1, tr("layout", self.language))
        self.right_tabs.setTabText(2, tr("templates", self.language))
        self.workspace_tabs.setTabText(0, tr("preview", self.language))
        self.workspace_tabs.setTabText(1, tr("data_preview", self.language))
        self.empty_title.setText(tr("empty_title", self.language))
        self.empty_text.setText(tr("empty_text", self.language))
        self.empty_button.setText(tr("open_data", self.language))
        self.source_title.setText(tr("source", self.language))
        self.source_label.setText(self.data_source or tr("no_data", self.language))
        self.import_button.setText(tr("open_data", self.language))
        self.sample_button.setText(tr("sample_data", self.language))
        self.generate_button.setText(tr("generate", self.language))
        self.grid_check.setText(tr("grid", self.language))
        self.legend_check.setText(tr("legend", self.language))
        self.tight_check.setText(tr("tight_layout", self.language))
        self.sort_check.setText(tr("sort_x", self.language))
        self.polar_degrees_check.setText(tr("polar_degrees", self.language))
        self.radar_normalize_check.setText(tr("radar_normalize", self.language))
        self.move_labels_button.setText(tr("move_labels", self.language))
        self.reset_labels_button.setText(tr("reset_labels", self.language))
        self.apply_template_button.setText(tr("apply_template", self.language))
        self.save_template_button.setText(tr("save_template", self.language))
        self.import_template_button.setText(tr("import_template", self.language))
        self.export_template_button.setText(tr("export_template", self.language))
        for key, labels in self.form_labels.items():
            for label in labels:
                label.setText(tr(key, self.language))
        current_chart = self.chart_combo.currentData() or self.current_settings.chart_type
        self.chart_combo.blockSignals(True)
        self.chart_combo.clear()
        for chart_id in CHART_DEFINITIONS:
            self.chart_combo.addItem(chart_label(chart_id, self.language), chart_id)
        index = self.chart_combo.findData(current_chart)
        self.chart_combo.setCurrentIndex(max(0, index))
        self.chart_combo.blockSignals(False)
        self._replace_combo_items(
            self.x_scale_combo,
            [(tr("linear", self.language), "linear"), (tr("log", self.language), "log"), (tr("symlog", self.language), "symlog")],
        )
        self._replace_combo_items(
            self.y_scale_combo,
            [(tr("linear", self.language), "linear"), (tr("log", self.language), "log"), (tr("symlog", self.language), "symlog")],
        )
        self._replace_combo_items(
            self.missing_combo,
            [
                (tr("missing_drop", self.language), "drop"),
                (tr("missing_interpolate", self.language), "interpolate"),
                (tr("missing_zero", self.language), "zero"),
            ],
        )
        self._replace_combo_items(
            self.legend_position_combo,
            [
                (tr("legend_auto", self.language), "auto"),
                (tr("legend_upper_right", self.language), "upper_right"),
                (tr("legend_upper_left", self.language), "upper_left"),
                (tr("legend_right", self.language), "right"),
                (tr("legend_bottom", self.language), "bottom"),
                (tr("legend_none", self.language), "none"),
            ],
        )
        self.status_label.setText(tr("ready", self.language))
        self._update_chart_controls()

    def _replace_combo_items(self, combo: QComboBox, items: list[tuple[str, Any]]) -> None:
        current = combo.currentData()
        combo.blockSignals(True)
        combo.clear()
        for label, value in items:
            combo.addItem(label, value)
        index = combo.findData(current)
        combo.setCurrentIndex(index if index >= 0 else 0)
        combo.blockSignals(False)

    def set_language(self, language: str) -> None:
        if language not in LANGUAGES:
            return
        self.language = language
        self.settings_store.setValue("language", language)
        self.retranslate_ui()

    def _set_busy(self, busy: bool, message: str = "", progress: int | None = None) -> None:
        self._busy_count = max(0, self._busy_count + (1 if busy else -1))
        active = self._busy_count > 0
        self.progress.setVisible(active)
        if active:
            self.progress.setRange(0, 0 if progress is None else 100)
            if progress is not None:
                self.progress.setValue(progress)
        if message:
            self.status_label.setText(message)

    def _run_worker(self, worker: FunctionWorker, on_result: Any, message: str = "") -> None:
        self._workers.add(worker)
        self._set_busy(True, message)
        worker.signals.result.connect(on_result)
        worker.signals.error.connect(self._worker_error)
        worker.signals.progress.connect(self._worker_progress)
        worker.signals.finished.connect(lambda item=worker: self._worker_finished(item))
        self.thread_pool.start(worker)

    def _worker_progress(self, value: int, message: str) -> None:
        self.progress.setRange(0, 100)
        self.progress.setValue(max(0, min(100, value)))
        if message:
            self.status_label.setText(message)

    def _worker_error(self, message: str, details: str) -> None:
        self.status_label.setText(message)
        dialog = QMessageBox(self)
        dialog.setIcon(QMessageBox.Icon.Critical)
        dialog.setWindowTitle(APP_NAME)
        dialog.setText(message)
        dialog.setDetailedText(details)
        dialog.exec()

    def _worker_finished(self, worker: FunctionWorker) -> None:
        self._workers.discard(worker)
        self._set_busy(False)

    def import_data(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, tr("open_data", self.language), str(Path.home()), "Data (*.csv *.tsv *.txt *.dat *.xlsx *.xls);;All files (*)")
        if path:
            self._load_data_path(Path(path))

    def _load_data_path(self, path: Path) -> None:
        worker = FunctionWorker(read_data_file, path)
        worker.signals.result.connect(lambda frame, source=str(path): self._apply_dataframe(frame, source))
        self._run_worker(worker, lambda _result: None, tr("loading", self.language))

    def load_sample_data(self) -> None:
        path = SAMPLE_DIR / "example_measurements.csv"
        if not path.exists():
            QMessageBox.warning(self, APP_NAME, "Sample data is missing.")
            return
        self._load_data_path(path)

    def _apply_dataframe(self, dataframe: pd.DataFrame, source: str, settings: PlotSettings | None = None, render: bool = False) -> None:
        self.undo_stack.clear()
        self.last_rendered_settings = None
        self.figure = None
        self.canvas = None
        self.drag_controller = None
        self.actions["move_labels"].setChecked(False)
        self._clear_figure_layout()
        self.dataframe = dataframe
        self.data_source = source
        self.engine.set_data(dataframe)
        self.table_model.set_dataframe(dataframe)
        self.source_label.setText(source)
        self.stats_label.setText(f"{len(dataframe):,} rows · {len(dataframe.columns):,} columns")
        self._populate_columns(settings)
        self._update_action_states()
        self.preview_stack.setCurrentIndex(0)
        self.left_tabs.setCurrentIndex(1)
        self.status_label.setText(f"{Path(source).name} · {len(dataframe):,} rows")
        if render and settings is not None:
            self.apply_settings(settings, render=True)

    def _populate_columns(self, settings: PlotSettings | None = None) -> None:
        columns = [str(column) for column in self.dataframe.columns]
        numeric = numeric_columns(self.dataframe)
        suggestions = suggest_columns(self.dataframe)
        for combo, values in (
            (self.x_combo, columns),
            (self.group_combo, columns),
            (self.error_combo, numeric),
            (self.z_combo, numeric),
            (self.size_combo, numeric),
            (self.color_combo, numeric),
        ):
            combo.clear()
            combo.addItem("", "")
            for value in values:
                combo.addItem(value, value)
        self.y_list.clear()
        for column in numeric:
            item = QListWidgetItem(column)
            item.setData(Qt.ItemDataRole.UserRole, column)
            self.y_list.addItem(item)
        target = settings or replace(
            self.current_settings,
            x_col=suggestions["x"],
            y_cols=suggestions["y"],
            z_col=suggestions["z"],
            error_col=suggestions["error"],
            group_col=suggestions["group"],
            size_col="",
            color_col="",
            title="",
            xlabel="",
            ylabel="",
            zlabel="",
            title_x=None,
            title_y=None,
            xlabel_x=None,
            xlabel_y=None,
            ylabel_x=None,
            ylabel_y=None,
            legend_x=None,
            legend_y=None,
        )
        self.current_settings = target
        self.apply_settings_to_controls(target)

    def _set_combo_data(self, combo: QComboBox, value: str) -> None:
        index = combo.findData(value)
        combo.setCurrentIndex(index if index >= 0 else 0)

    def _selected_y_columns(self) -> list[str]:
        return [str(item.data(Qt.ItemDataRole.UserRole)) for item in self.y_list.selectedItems()]

    def _select_y_columns(self, columns: list[str]) -> None:
        wanted = set(columns)
        selection_model = self.y_list.selectionModel()
        selection_model.clearSelection()
        for row in range(self.y_list.count()):
            item = self.y_list.item(row)
            if str(item.data(Qt.ItemDataRole.UserRole)) in wanted:
                index = self.y_list.model().index(row, 0)
                selection_model.select(index, QItemSelectionModel.SelectionFlag.Select)

    def _update_chart_controls(self) -> None:
        chart_type = str(self.chart_combo.currentData() or "line")
        requirements = chart_requirements(chart_type)
        visibility = {
            "x_column": requirements["x"],
            "y_columns": requirements["y"],
            "z_column": requirements["z"],
            "error_column": requirements["error"],
            "group_column": requirements["group"],
            "size_column": requirements["size"],
            "color_column": requirements["color"],
            "zlabel": requirements["z"],
        }
        for key, (label, widget) in self.plot_rows.items():
            visible = visibility.get(key, True)
            label.setVisible(visible)
            widget.setVisible(visible)
        for key, (label, widget) in self.style_rows.items():
            visible = True
            if key == "bins":
                visible = requirements["bins"]
            elif key in {"elevation", "azimuth"}:
                visible = requirements["3d"]
            label.setVisible(visible)
            widget.setVisible(visible)
        self.polar_degrees_check.setVisible(requirements["polar"])
        self.radar_normalize_check.setVisible(requirements["radar"])
        self.y_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection if requirements["single_y"] else QAbstractItemView.SelectionMode.ExtendedSelection)

    def collect_settings(self) -> PlotSettings:
        return PlotSettings(
            chart_type=str(self.chart_combo.currentData() or "line"),
            x_col=str(self.x_combo.currentData() or ""),
            y_cols=self._selected_y_columns(),
            z_col=str(self.z_combo.currentData() or ""),
            error_col=str(self.error_combo.currentData() or ""),
            group_col=str(self.group_combo.currentData() or ""),
            size_col=str(self.size_combo.currentData() or ""),
            color_col=str(self.color_combo.currentData() or ""),
            title=self.title_edit.text(),
            xlabel=self.xlabel_edit.text(),
            ylabel=self.ylabel_edit.text(),
            zlabel=self.zlabel_edit.text(),
            width=self.width_spin.value(),
            height=self.height_spin.value(),
            dpi=self.dpi_spin.value(),
            font_size=self.font_spin.value(),
            line_width=self.line_width_spin.value(),
            marker_size=self.marker_size_spin.value(),
            marker=str(self.marker_combo.currentData() or ""),
            palette=str(self.palette_combo.currentData() or "SciPlot Classic"),
            grid=self.grid_check.isChecked(),
            legend=self.legend_check.isChecked(),
            tight_layout=self.tight_check.isChecked(),
            title_pad=self.title_pad_spin.value(),
            axis_label_pad=self.axis_pad_spin.value(),
            tick_label_pad=self.tick_pad_spin.value(),
            x_tick_rotation=self.rotation_spin.value(),
            legend_position=str(self.legend_position_combo.currentData() or "auto"),
            margin_left=self.left_margin_spin.value(),
            margin_right=self.right_margin_spin.value(),
            margin_top=self.top_margin_spin.value(),
            margin_bottom=self.bottom_margin_spin.value(),
            bins=self.bins_spin.value(),
            elev=self.elev_spin.value(),
            azim=self.azim_spin.value(),
            x_scale=str(self.x_scale_combo.currentData() or "linear"),
            y_scale=str(self.y_scale_combo.currentData() or "linear"),
            missing_policy=str(self.missing_combo.currentData() or "drop"),
            sort_x=self.sort_check.isChecked(),
            polar_degrees=self.polar_degrees_check.isChecked(),
            radar_normalize=self.radar_normalize_check.isChecked(),
            title_x=self.current_settings.title_x,
            title_y=self.current_settings.title_y,
            xlabel_x=self.current_settings.xlabel_x,
            xlabel_y=self.current_settings.xlabel_y,
            ylabel_x=self.current_settings.ylabel_x,
            ylabel_y=self.current_settings.ylabel_y,
            legend_x=self.current_settings.legend_x,
            legend_y=self.current_settings.legend_y,
        )

    def apply_settings_to_controls(self, settings: PlotSettings) -> None:
        self._applying_settings = True
        try:
            self._set_combo_data(self.chart_combo, settings.chart_type)
            self._set_combo_data(self.x_combo, settings.x_col)
            self._set_combo_data(self.z_combo, settings.z_col)
            self._set_combo_data(self.error_combo, settings.error_col)
            self._set_combo_data(self.group_combo, settings.group_col)
            self._set_combo_data(self.size_combo, settings.size_col)
            self._set_combo_data(self.color_combo, settings.color_col)
            self._select_y_columns(settings.y_cols or [])
            self.title_edit.setText(settings.title)
            self.xlabel_edit.setText(settings.xlabel)
            self.ylabel_edit.setText(settings.ylabel)
            self.zlabel_edit.setText(settings.zlabel)
            self.width_spin.setValue(settings.width)
            self.height_spin.setValue(settings.height)
            self.dpi_spin.setValue(settings.dpi)
            self.font_spin.setValue(settings.font_size)
            self.line_width_spin.setValue(settings.line_width)
            self.marker_size_spin.setValue(settings.marker_size)
            self._set_combo_data(self.marker_combo, settings.marker)
            self._set_combo_data(self.palette_combo, settings.palette)
            self.bins_spin.setValue(settings.bins)
            self.elev_spin.setValue(settings.elev)
            self.azim_spin.setValue(settings.azim)
            self.grid_check.setChecked(settings.grid)
            self.legend_check.setChecked(settings.legend)
            self.tight_check.setChecked(settings.tight_layout)
            self.sort_check.setChecked(settings.sort_x)
            self.polar_degrees_check.setChecked(settings.polar_degrees)
            self.radar_normalize_check.setChecked(settings.radar_normalize)
            self._set_combo_data(self.x_scale_combo, settings.x_scale)
            self._set_combo_data(self.y_scale_combo, settings.y_scale)
            self._set_combo_data(self.missing_combo, settings.missing_policy)
            self.title_pad_spin.setValue(settings.title_pad)
            self.axis_pad_spin.setValue(settings.axis_label_pad)
            self.tick_pad_spin.setValue(settings.tick_label_pad)
            self.rotation_spin.setValue(settings.x_tick_rotation)
            self._set_combo_data(self.legend_position_combo, settings.legend_position)
            self.left_margin_spin.setValue(settings.margin_left)
            self.right_margin_spin.setValue(settings.margin_right)
            self.top_margin_spin.setValue(settings.margin_top)
            self.bottom_margin_spin.setValue(settings.margin_bottom)
            self._update_chart_controls()
        finally:
            self._applying_settings = False

    def generate_figure(self) -> None:
        if self.dataframe.empty:
            QMessageBox.warning(self, APP_NAME, tr("no_data", self.language))
            return
        settings = self.collect_settings()
        if settings.chart_type in {"line", "step"} and not settings.group_col and settings.x_col:
            x = self.dataframe[settings.x_col]
            if x.duplicated().any():
                message = "Repeated X values were detected. Select a group column to avoid connecting unrelated series."
                if self.language == "zh_TW":
                    message = "檢測到重複 X 值。建議選擇分組欄位，避免連接不相關的數據系列。"
                elif self.language == "zh_CN":
                    message = "检测到重复 X 值。建议选择分组字段，避免连接不相关的数据系列。"
                if QMessageBox.question(self, APP_NAME, message, QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel) != QMessageBox.StandardButton.Ok:
                    return
        if self.last_rendered_settings is None:
            self.apply_settings(settings, render=True)
        elif settings != self.current_settings:
            self.undo_stack.push(SettingsCommand(self, self.current_settings, settings, tr("generate", self.language)))
        else:
            self.render_settings(settings)

    def apply_settings(self, settings: PlotSettings, render: bool = False) -> None:
        self.current_settings = settings
        self.apply_settings_to_controls(settings)
        if render and not self.dataframe.empty:
            self.render_settings(settings)

    def render_settings(self, settings: PlotSettings) -> None:
        try:
            figure = self.engine.create_figure(settings)
            self.current_settings = settings
            self.last_rendered_settings = settings
            self._display_figure(figure)
            self.status_label.setText(f"{tr('rendered', self.language)} · {chart_label(settings.chart_type, self.language)}")
            self._save_session_async()
        except Exception as exc:
            QMessageBox.critical(self, APP_NAME, str(exc))

    def _clear_figure_layout(self) -> None:
        while self.figure_layout.count():
            item = self.figure_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _display_figure(self, figure: Figure) -> None:
        self._clear_figure_layout()
        self.figure = figure
        self.canvas = FigureCanvasQTAgg(figure)
        navigation = NavigationToolbar2QT(self.canvas, self.figure_page)
        navigation.setIconSize(navigation.iconSize())
        self.figure_layout.addWidget(navigation)
        self.figure_layout.addWidget(self.canvas, 1)
        self.drag_controller = LabelDragController(self.canvas, self._label_moved)
        self.drag_controller.set_figure(figure)
        self.drag_controller.set_enabled(self.actions["move_labels"].isChecked())
        self.canvas.draw()
        self.preview_stack.setCurrentIndex(1)
        self.workspace_tabs.setCurrentIndex(0)
        self._update_action_states()

    def toggle_label_dragging(self, enabled: bool) -> None:
        if self.drag_controller:
            self.drag_controller.set_enabled(enabled)
        self.status_label.setText(tr("move_labels", self.language) if enabled else tr("ready", self.language))

    def _label_moved(self, name: str, x: float, y: float) -> None:
        before = self.current_settings
        values = before.to_dict()
        values[f"{name}_x"] = x
        values[f"{name}_y"] = y
        after = PlotSettings.from_dict(values)
        self.current_settings = after
        self.last_rendered_settings = after
        self.undo_stack.push(SettingsCommand(self, before, after, tr("move_labels", self.language), skip_first_redo=True))
        self._save_session_async()

    def reset_label_positions(self) -> None:
        if self.last_rendered_settings is None:
            return
        before = self.current_settings
        after = replace(before, title_x=None, title_y=None, xlabel_x=None, xlabel_y=None, ylabel_x=None, ylabel_y=None, legend_x=None, legend_y=None)
        self.undo_stack.push(SettingsCommand(self, before, after, tr("reset_labels", self.language)))

    def _suggested_export_name(self) -> str:
        name = self.current_settings.title.strip() or "sciplot_figure"
        safe = re.sub(r"[^\w.-]+", "_", name, flags=re.UNICODE).strip("._")
        return (safe or "sciplot_figure")[:100]

    def export_figure(self) -> None:
        if self.figure is None or self.dataframe.empty:
            QMessageBox.warning(self, APP_NAME, "Generate a figure before exporting.")
            return
        dialog = ExportDialog(self, self.language, self._suggested_export_name(), self.current_settings.dpi)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        path, dpi, transparent = dialog.values()
        if path.suffix.lower() not in {".png", ".svg", ".pdf"}:
            path = path.with_suffix(".png")
        worker = FunctionWorker(save_figure, self.dataframe.copy(deep=False), self.current_settings, str(path), dpi, transparent)
        self._run_worker(worker, lambda _result, output=path: self.status_label.setText(str(output)), tr("export", self.language))

    def save_project(self) -> None:
        if self.dataframe.empty:
            QMessageBox.warning(self, APP_NAME, tr("no_data", self.language))
            return
        path, _ = QFileDialog.getSaveFileName(self, tr("save_project", self.language), str(PROJECT_DIR / "project.sciplot"), "SciPlot Project (*.sciplot)")
        if not path:
            return
        settings = self.collect_settings()
        worker = FunctionWorker(save_project, Path(path), self.dataframe.copy(deep=False), settings, Path(self.data_source).name if self.data_source else "")
        self._run_worker(worker, lambda output: self.status_label.setText(str(output)), tr("save_project", self.language))

    def open_project(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, tr("open_project", self.language), str(PROJECT_DIR), "SciPlot Project (*.sciplot *.json);;All files (*)")
        if not path:
            return
        worker = FunctionWorker(load_project, Path(path))
        self._run_worker(worker, lambda project, source=path: self._apply_project(project, source), tr("open_project", self.language))

    def _apply_project(self, project: ProjectData, source: str) -> None:
        self.undo_stack.clear()
        self.last_rendered_settings = None
        self._apply_dataframe(project.dataframe, project.source_name or source, project.settings, render=True)

    def _save_session_async(self) -> None:
        if self.dataframe.empty or self.last_rendered_settings is None:
            return
        worker = FunctionWorker(save_session, SESSION_PATH, self.dataframe.copy(deep=False), self.last_rendered_settings, self.data_source)
        self._workers.add(worker)
        worker.signals.finished.connect(lambda item=worker: self._workers.discard(item))
        self.session_thread_pool.start(worker)

    def restore_last_session(self) -> None:
        try:
            session = load_session(SESSION_PATH)
            if session:
                self._apply_dataframe(session.dataframe, session.source_path or session.source_name, session.settings, render=True)
        except SessionSourceChangedError:
            message = "The source data changed after the last session, so SciPlot did not restore the old figure."
            QMessageBox.warning(self, APP_NAME, message)
        except Exception as exc:
            self.status_label.setText(f"Session restore failed: {exc}")

    def new_workspace(self) -> None:
        if not self.dataframe.empty and QMessageBox.question(self, APP_NAME, "Clear the current workspace?") != QMessageBox.StandardButton.Yes:
            return
        self.session_thread_pool.waitForDone()
        self.dataframe = pd.DataFrame()
        self.data_source = ""
        self.engine.set_data(self.dataframe)
        self.table_model.set_dataframe(self.dataframe)
        self.current_settings = PlotSettings()
        self.last_rendered_settings = None
        self.figure = None
        self.canvas = None
        self.drag_controller = None
        self.undo_stack.clear()
        self._clear_figure_layout()
        self.preview_stack.setCurrentIndex(0)
        self.source_label.setText(tr("no_data", self.language))
        self.stats_label.setText("0 rows · 0 columns")
        self._update_action_states()
        SESSION_PATH.unlink(missing_ok=True)

    def refresh_templates(self) -> None:
        current = self.template_combo.currentData() if hasattr(self, "template_combo") else None
        self.template_combo.clear()
        for path in sorted(TEMPLATE_DIR.glob("*.json")):
            self.template_combo.addItem(path.stem.replace("_", " "), str(path))
        if current:
            index = self.template_combo.findData(current)
            if index >= 0:
                self.template_combo.setCurrentIndex(index)

    def _style_template(self) -> dict[str, Any]:
        payload = self.collect_settings().to_dict()
        for key in DATA_FIELDS:
            payload.pop(key, None)
        return payload

    def apply_template(self) -> None:
        path = Path(str(self.template_combo.currentData() or ""))
        if not path.exists():
            return
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            merged = self.collect_settings().to_dict()
            merged.update(payload)
            after = PlotSettings.from_dict(merged)
            if self.last_rendered_settings is None:
                self.apply_settings(after, render=False)
            else:
                self.undo_stack.push(SettingsCommand(self, self.current_settings, after, tr("apply_template", self.language)))
        except Exception as exc:
            QMessageBox.critical(self, APP_NAME, str(exc))

    def save_template(self) -> None:
        name, accepted = QInputDialog.getText(self, tr("save_template", self.language), tr("title", self.language))
        if not accepted:
            return
        safe = re.sub(r"[^\w-]+", "_", name.strip(), flags=re.UNICODE).strip("_")
        if not safe:
            return
        path = TEMPLATE_DIR / f"{safe}.json"
        path.write_text(json.dumps(self._style_template(), ensure_ascii=False, indent=2), encoding="utf-8")
        self.refresh_templates()
        self._set_combo_data(self.template_combo, str(path))

    def import_template(self) -> None:
        source, _ = QFileDialog.getOpenFileName(self, tr("import_template", self.language), str(Path.home()), "JSON (*.json)")
        if not source:
            return
        try:
            payload = json.loads(Path(source).read_text(encoding="utf-8"))
            PlotSettings.from_dict(payload)
            destination = TEMPLATE_DIR / Path(source).name
            destination.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            self.refresh_templates()
        except Exception as exc:
            QMessageBox.critical(self, APP_NAME, str(exc))

    def export_template(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, tr("export_template", self.language), str(PROJECT_DIR / "sciplot_style.json"), "JSON (*.json)")
        if path:
            Path(path).write_text(json.dumps(self._style_template(), ensure_ascii=False, indent=2), encoding="utf-8")

    def _set_auto_updates(self, enabled: bool) -> None:
        self.settings_store.setValue("auto_updates", enabled)

    def _auto_check_updates(self) -> None:
        last = int(self.settings_store.value("last_update_check", 0) or 0)
        if time.time() - last >= 24 * 60 * 60:
            self.settings_store.setValue("last_update_check", int(time.time()))
            self.check_for_updates(silent=True)

    def check_for_updates(self, silent: bool = False) -> None:
        worker = FunctionWorker(fetch_latest_release)
        worker.signals.error.connect(lambda message, _details: None if silent else QMessageBox.warning(self, APP_NAME, message))
        self._workers.add(worker)
        worker.signals.result.connect(lambda info: self._handle_update_info(info, silent))
        worker.signals.finished.connect(lambda item=worker: self._workers.discard(item))
        if not silent:
            self.status_label.setText(tr("check_updates", self.language))
        self.thread_pool.start(worker)

    def _handle_update_info(self, info: UpdateInfo | None, silent: bool) -> None:
        if info is None:
            if not silent:
                QMessageBox.information(self, APP_NAME, f"SciPlot {APP_VERSION} is up to date.")
            return
        dialog = QMessageBox(self)
        dialog.setIcon(QMessageBox.Icon.Information)
        dialog.setWindowTitle(APP_NAME)
        dialog.setText(f"SciPlot {info.version} is available.")
        download_button = dialog.addButton("Download", QMessageBox.ButtonRole.AcceptRole) if info.asset_url else None
        release_button = dialog.addButton("Open release page", QMessageBox.ButtonRole.ActionRole)
        dialog.addButton(QMessageBox.StandardButton.Cancel)
        dialog.exec()
        clicked = dialog.clickedButton()
        if clicked == release_button:
            QDesktopServices.openUrl(QUrl(info.release_url))
        elif download_button is not None and clicked == download_button:
            self._download_update(info)

    def _download_update(self, info: UpdateInfo) -> None:
        destination = UPDATE_DIR / Path(info.asset_name).name
        worker = FunctionWorker(download_update, info, destination, with_progress=True)
        self._run_worker(worker, self._open_downloaded_update, f"Downloading SciPlot {info.version}")

    def _open_downloaded_update(self, path: Path) -> None:
        if QMessageBox.question(self, APP_NAME, f"Open installer?\n{path}") != QMessageBox.StandardButton.Yes:
            return
        try:
            if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.resolve()))):
                raise OSError("The operating system did not accept the installer file.")
        except Exception as exc:
            QMessageBox.critical(self, APP_NAME, str(exc))

    def show_about(self) -> None:
        QMessageBox.about(self, tr("about", self.language), f"<h2>{APP_NAME} {APP_VERSION}</h2><p>{tr('app_subtitle', self.language)}</p><p>Python · PySide6 · pandas · Matplotlib · SciPy</p>")

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802
        if any(url.isLocalFile() for url in event.mimeData().urls()):
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        paths = [Path(url.toLocalFile()) for url in event.mimeData().urls() if url.isLocalFile()]
        if paths:
            path = paths[0]
            if path.suffix.lower() in {".sciplot", ".json"}:
                worker = FunctionWorker(load_project, path)
                self._run_worker(worker, lambda project, source=str(path): self._apply_project(project, source), tr("open_project", self.language))
            else:
                self._load_data_path(path)
            event.acceptProposedAction()

    def _restore_window_state(self) -> None:
        geometry = self.settings_store.value("window_geometry")
        state = self.settings_store.value("window_state")
        if geometry:
            self.restoreGeometry(geometry)
        if state:
            self.restoreState(state)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        self.settings_store.setValue("window_geometry", self.saveGeometry())
        self.settings_store.setValue("window_state", self.saveState())
        self.session_thread_pool.waitForDone()
        event.accept()

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._update_responsive_docks(event.size().width())

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
        super().showEvent(event)
        QTimer.singleShot(0, lambda: self._update_responsive_docks(self.width()))

    def _update_responsive_docks(self, width: int) -> None:
        if not hasattr(self, "right_dock") or self.right_dock.isFloating():
            return
        self.main_toolbar.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonIconOnly if width < 1100 else Qt.ToolButtonStyle.ToolButtonTextBesideIcon
        )
        if width < 1100 and self.right_dock.isVisible():
            self._right_auto_hidden = True
            self.right_dock.hide()
        elif width >= 1250 and self._right_auto_hidden:
            self._right_auto_hidden = False
            self.right_dock.show()
