from __future__ import annotations

import json
import os
import platform
import re
import subprocess
import sys
import threading
import urllib.error
import urllib.request
import warnings
import webbrowser
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any


APP_NAME = "SciPlot"
APP_VERSION = "2.1.7"
MAX_SESSION_RECORDS = 5000
GITHUB_RELEASES_URL = "https://github.com/Kevin-kaiquan/SciPlot/releases"
GITHUB_LATEST_RELEASE_API = "https://api.github.com/repos/Kevin-kaiquan/SciPlot/releases/latest"


def get_app_home() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


APP_HOME = get_app_home()


def can_write_to(directory: Path) -> bool:
    try:
        directory.mkdir(parents=True, exist_ok=True)
        probe = directory / ".sciplot_write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True
    except OSError:
        return False


def get_user_data_home() -> Path:
    override = os.environ.get("SCIPLOT_APP_DATA_DIR")
    if override:
        return Path(override).expanduser()
    if not getattr(sys, "frozen", False):
        return APP_HOME
    if not (APP_HOME / "sciplot_installed.flag").exists() and can_write_to(APP_HOME):
        return APP_HOME
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    if base:
        return Path(base) / APP_NAME
    return Path.home() / f".{APP_NAME.lower()}"


APP_DATA_HOME = get_user_data_home()
RUNTIME_DIR = APP_DATA_HOME / "runtime"
RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(RUNTIME_DIR / "matplotlib"))

import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

import numpy as np
import pandas as pd
import matplotlib.tri as mtri
from matplotlib import rcParams
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure
from matplotlib.patches import Circle
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401 - required for PyInstaller 3D projection collection
from PIL import Image, ImageTk


RESOURCE_ROOT = Path(getattr(sys, "_MEIPASS", APP_HOME))
PACKAGE_TEMPLATE_DIR = RESOURCE_ROOT / "templates"
TEMPLATE_DIR = APP_DATA_HOME / "templates"
SAMPLE_DIR = RESOURCE_ROOT / "sample_data"
USER_DATA_DIR = APP_DATA_HOME / "user_data"
EXPORT_DIR = APP_DATA_HOME / "exports"
STATE_PATH = APP_DATA_HOME / "last_session.json"
LOGO_DIR = RESOURCE_ROOT / "logo"
APP_ICON_PNG = LOGO_DIR / "SciPlot.png"
APP_ICON_ICO = LOGO_DIR / "SciPlot.ico"

for directory in (TEMPLATE_DIR, USER_DATA_DIR, EXPORT_DIR, RUNTIME_DIR / "matplotlib"):
    directory.mkdir(parents=True, exist_ok=True)


def seed_packaged_files() -> None:
    if PACKAGE_TEMPLATE_DIR.exists():
        for source in PACKAGE_TEMPLATE_DIR.glob("*.json"):
            destination = TEMPLATE_DIR / source.name
            if not destination.exists():
                destination.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")


seed_packaged_files()

rcParams["font.sans-serif"] = [
    "Microsoft YaHei",
    "SimHei",
    "Arial Unicode MS",
    "DejaVu Sans",
]
rcParams["axes.unicode_minus"] = False


CHART_TYPES = {
    "折線圖": "line",
    "階梯圖": "step",
    "面積圖": "area",
    "堆疊面積圖": "stacked_area",
    "散點圖": "scatter",
    "氣泡圖": "bubble",
    "柱狀圖": "bar",
    "水平柱狀圖": "barh",
    "誤差棒": "errorbar",
    "直方圖": "histogram",
    "密度曲線": "density",
    "累積分布 ECDF": "ecdf",
    "箱線圖": "boxplot",
    "小提琴圖": "violin",
    "莖葉圖 Stem": "stem",
    "棒棒糖圖": "lollipop",
    "相關熱圖": "heatmap",
    "二維直方圖": "hist2d",
    "六邊形密度圖": "hexbin",
    "等高線圖": "contour",
    "填色等高線圖": "contourf",
    "雷達圖": "radar",
    "極坐標折線圖": "polar_line",
    "極坐標散點圖": "polar_scatter",
    "餅圖": "pie",
    "環形圖": "donut",
    "3D 散點圖": "scatter3d",
    "3D 折線圖": "line3d",
    "3D 曲面圖": "surface3d",
    "3D 網格圖": "wireframe3d",
    "3D 柱狀圖": "bar3d",
    "3D 等高線圖": "contour3d",
}

CHART_GROUPS = {
    "Core": {"line", "step", "area", "stacked_area", "scatter", "bubble", "bar", "barh", "errorbar"},
    "Distributions": {"histogram", "density", "ecdf", "boxplot", "violin", "stem", "lollipop"},
    "Matrices & Density": {"heatmap", "hist2d", "hexbin", "contour", "contourf"},
    "Polar & Composition": {"radar", "polar_line", "polar_scatter", "pie", "donut"},
    "3D": {"scatter3d", "line3d", "surface3d", "wireframe3d", "bar3d", "contour3d"},
}

PALETTES = {
    "SciPlot Classic": ["#2563eb", "#ef4444", "#111827", "#60a5fa", "#f59e0b", "#10b981"],
    "期刊藍灰": ["#1f5f8b", "#c44e52", "#55a868", "#8172b3", "#ccb974", "#64b5cd"],
    "色盲友好": ["#0072B2", "#D55E00", "#009E73", "#CC79A7", "#F0E442", "#56B4E9"],
    "單色灰階": ["#111827", "#374151", "#6b7280", "#9ca3af", "#d1d5db", "#4b5563"],
    "實驗室暖色": ["#8c2d04", "#cc4c02", "#ec7014", "#fe9929", "#fec44f", "#fff7bc"],
    "對比冷色": ["#003f5c", "#2f4b7c", "#665191", "#a05195", "#d45087", "#f95d6a"],
}


BUILTIN_TEMPLATES: dict[str, dict[str, Any]] = {
    "SciPlot Classic": {
        "chart_type": "折線圖",
        "width": 7.2,
        "height": 4.2,
        "dpi": 300,
        "font_size": 10,
        "line_width": 1.6,
        "marker_size": 4.5,
        "marker": "o",
        "palette": "SciPlot Classic",
        "grid": True,
        "legend": True,
        "tight_layout": True,
    },
    "Nature 清爽雙欄": {
        "chart_type": "折線圖",
        "width": 7.2,
        "height": 4.2,
        "dpi": 300,
        "font_size": 10,
        "line_width": 1.8,
        "marker_size": 5,
        "marker": "o",
        "palette": "期刊藍灰",
        "grid": True,
        "legend": True,
        "tight_layout": True,
    },
    "IEEE 單色出版": {
        "chart_type": "折線圖",
        "width": 6.9,
        "height": 4.0,
        "dpi": 600,
        "font_size": 9,
        "line_width": 1.5,
        "marker_size": 4,
        "marker": "s",
        "palette": "單色灰階",
        "grid": True,
        "legend": True,
        "tight_layout": True,
    },
    "課堂展示高對比": {
        "chart_type": "柱狀圖",
        "width": 9.0,
        "height": 5.4,
        "dpi": 200,
        "font_size": 12,
        "line_width": 2.0,
        "marker_size": 6,
        "marker": "o",
        "palette": "色盲友好",
        "grid": True,
        "legend": True,
        "tight_layout": True,
    },
    "相關矩陣熱圖": {
        "chart_type": "相關熱圖",
        "width": 6.5,
        "height": 5.8,
        "dpi": 300,
        "font_size": 10,
        "line_width": 1.0,
        "marker_size": 4,
        "marker": "o",
        "palette": "對比冷色",
        "grid": False,
        "legend": False,
        "tight_layout": True,
    },
}


@dataclass
class PlotSettings:
    chart_type: str = "折線圖"
    x_col: str = ""
    y_cols: list[str] | None = None
    z_col: str = ""
    error_col: str = ""
    group_col: str = ""
    size_col: str = ""
    color_col: str = ""
    title: str = ""
    xlabel: str = ""
    ylabel: str = ""
    zlabel: str = ""
    width: float = 7.2
    height: float = 4.2
    dpi: int = 300
    font_size: int = 10
    line_width: float = 1.8
    marker_size: float = 5.0
    marker: str = "o"
    palette: str = "SciPlot Classic"
    grid: bool = True
    legend: bool = True
    tight_layout: bool = True
    title_pad: int = 14
    axis_label_pad: int = 8
    tick_label_pad: int = 4
    x_tick_rotation: int = 0
    legend_position: str = "自動"
    margin_left: float = 0.0
    margin_right: float = 0.0
    margin_top: float = 0.0
    margin_bottom: float = 0.0
    bins: int = 30
    elev: int = 28
    azim: int = -55


class ScrollFrame(ttk.Frame):
    def __init__(self, parent: tk.Widget, width: int = 286) -> None:
        super().__init__(parent)
        self.canvas = tk.Canvas(self, width=width, highlightthickness=0, borderwidth=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = ttk.Frame(self.canvas)
        self.window = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")

        self.inner.bind("<Configure>", self._on_inner_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.scrollbar.grid(row=0, column=1, sticky="ns")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

    def _on_inner_configure(self, _event: tk.Event) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event: tk.Event) -> None:
        self.canvas.itemconfigure(self.window, width=event.width)


class SciPlotApp(tk.Tk):
    def __init__(self, visible: bool = True) -> None:
        super().__init__()
        if not visible:
            self.withdraw()
        self.title(f"{APP_NAME} {APP_VERSION}")
        self._set_initial_geometry()

        self.df = pd.DataFrame()
        self.data_source = ""
        self._numeric_cache: dict[str, pd.Series] = {}
        self._update_check_running = False
        self.figure: Figure | None = None
        self.canvas_widget: FigureCanvasTkAgg | None = None
        self.toolbar: NavigationToolbar2Tk | None = None
        self.current_settings = PlotSettings()

        self._vars: dict[str, tk.Variable] = {}
        self._build_style()
        self._build_ui()
        self._load_last_session()
        self._apply_window_icon()

    def _set_initial_geometry(self) -> None:
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        width = min(1280, max(1080, screen_w - 180))
        height = min(820, max(700, screen_h - 140))
        self.minsize(min(1080, width), min(700, height))
        x = 40 if screen_w > width + 80 else max(0, (screen_w - width) // 2)
        y = 40 if screen_h > height + 80 else max(0, (screen_h - height) // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")

    def _apply_window_icon(self) -> None:
        try:
            if APP_ICON_ICO.exists() and sys.platform.startswith("win"):
                self.iconbitmap(str(APP_ICON_ICO))
            if APP_ICON_PNG.exists():
                self._icon_image = tk.PhotoImage(file=str(APP_ICON_PNG))
                self.iconphoto(True, self._icon_image)
        except tk.TclError:
            pass

    def _load_logo_photo(self, max_size: int) -> ImageTk.PhotoImage | None:
        try:
            if not APP_ICON_PNG.exists():
                return None
            image = Image.open(APP_ICON_PNG).convert("RGBA")
            image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
            return ImageTk.PhotoImage(image)
        except Exception:
            return None

    def _build_style(self) -> None:
        self.colors = {
            "app": "#f3f6fb",
            "surface": "#ffffff",
            "surface_2": "#f8fafc",
            "border": "#d9e2f1",
            "text": "#111827",
            "muted": "#5f6f85",
            "primary": "#1f66f2",
            "primary_dark": "#174fbf",
            "sidebar": "#0b1833",
            "sidebar_2": "#132a55",
            "sidebar_active": "#246bfe",
        }
        self.configure(bg=self.colors["app"])
        self.option_add("*Font", ("Microsoft YaHei UI", 10))
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure(".", font=("Microsoft YaHei UI", 10), background=self.colors["app"])
        style.configure("TFrame", background=self.colors["app"])
        style.configure("App.TFrame", background=self.colors["app"])
        style.configure("Surface.TFrame", background=self.colors["surface"])
        style.configure("Card.TFrame", background=self.colors["surface"])
        style.configure("TLabel", background=self.colors["app"], foreground=self.colors["text"])
        style.configure("Surface.TLabel", background=self.colors["surface"], foreground=self.colors["text"])
        style.configure("Muted.TLabel", background=self.colors["surface"], foreground=self.colors["muted"])
        style.configure("Hero.TLabel", background=self.colors["app"], foreground=self.colors["text"], font=("Microsoft YaHei UI", 22, "bold"))
        style.configure("Subhero.TLabel", background=self.colors["app"], foreground=self.colors["muted"], font=("Microsoft YaHei UI", 11))
        style.configure("CardTitle.TLabel", background=self.colors["surface"], foreground=self.colors["text"], font=("Microsoft YaHei UI", 12, "bold"))
        style.configure("TButton", padding=(12, 7), background=self.colors["surface"], font=("Microsoft YaHei UI", 10, "bold"))
        style.configure("Tool.TButton", padding=(10, 7), background=self.colors["surface"], font=("Microsoft YaHei UI", 10, "bold"))
        style.configure("Accent.TButton", padding=(14, 8), foreground="#ffffff", background=self.colors["primary"], font=("Microsoft YaHei UI", 10, "bold"))
        style.map("Accent.TButton", background=[("active", self.colors["primary_dark"])])
        style.configure("Title.TLabel", background=self.colors["surface"], foreground=self.colors["text"], font=("Microsoft YaHei UI", 13, "bold"))
        style.configure("Status.TLabel", background=self.colors["app"], foreground="#4b5563", font=("Microsoft YaHei UI", 10))
        style.configure("TNotebook", background=self.colors["surface"], borderwidth=0)
        style.configure("TNotebook.Tab", padding=(16, 9), background="#eef2f7", font=("Microsoft YaHei UI", 10, "bold"))
        style.map("TNotebook.Tab", background=[("selected", "#ffffff")], foreground=[("selected", self.colors["primary"])])
        style.configure("Treeview", rowheight=29, bordercolor=self.colors["border"], lightcolor=self.colors["border"], darkcolor=self.colors["border"], font=("Microsoft YaHei UI", 10))
        style.configure("Treeview.Heading", font=("Microsoft YaHei UI", 10, "bold"))

    def _build_ui(self) -> None:
        self._build_menu()

        self.nav_buttons: dict[str, tk.Button] = {}
        self.status_var = tk.StringVar(value="就緒。")

        self.columnconfigure(0, weight=0)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        self._build_sidebar()

        shell = ttk.Frame(self, style="App.TFrame", padding=(18, 14, 18, 8))
        shell.grid(row=0, column=1, sticky="nsew")
        shell.columnconfigure(0, weight=1)
        shell.rowconfigure(1, weight=1)

        self.header_title_var = tk.StringVar(value="首頁")
        self.header_subtitle_var = tk.StringVar(value="導入數據、創建圖表、套用模板，然後導出論文可用圖片。")
        header = ttk.Frame(shell, style="App.TFrame")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        header.columnconfigure(0, weight=1)
        ttk.Label(header, textvariable=self.header_title_var, style="Hero.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(header, textvariable=self.header_subtitle_var, style="Subhero.TLabel").grid(row=1, column=0, sticky="w", pady=(4, 0))
        ttk.Button(header, text="載入數據", style="Tool.TButton", command=self.open_data).grid(row=0, column=1, rowspan=2, padx=(8, 0))
        ttk.Button(header, text="保存項目", style="Tool.TButton", command=self.save_project).grid(row=0, column=2, rowspan=2, padx=(8, 0))
        ttk.Button(header, text="導出圖表", style="Accent.TButton", command=self.open_export_dialog).grid(row=0, column=3, rowspan=2, padx=(8, 0))

        self.page_container = ttk.Frame(shell, style="App.TFrame")
        self.page_container.grid(row=1, column=0, sticky="nsew")
        self.page_container.columnconfigure(0, weight=1)
        self.page_container.rowconfigure(0, weight=1)

        self.pages: dict[str, ttk.Frame] = {}
        home = ttk.Frame(self.page_container, style="App.TFrame")
        workbench = ttk.Frame(self.page_container, style="App.TFrame")
        for page in (home, workbench):
            page.grid(row=0, column=0, sticky="nsew")
        self.pages["home"] = home
        self.pages["workbench"] = workbench
        self._build_home_page(home)
        self._build_workbench_page(workbench)

        status = ttk.Label(shell, textvariable=self.status_var, style="Status.TLabel", padding=(2, 6))
        status.grid(row=2, column=0, sticky="ew")
        self.navigate("home")

    def _build_sidebar(self) -> None:
        sidebar = tk.Frame(self, bg=self.colors["sidebar"], width=168)
        sidebar.grid(row=0, column=0, sticky="ns")
        sidebar.grid_propagate(False)
        sidebar.columnconfigure(0, weight=1)

        brand = tk.Frame(sidebar, bg=self.colors["sidebar"])
        brand.grid(row=0, column=0, sticky="ew", padx=10, pady=(18, 12))
        brand.columnconfigure(0, weight=1)
        self._sidebar_logo_image = self._load_logo_photo(88)
        if self._sidebar_logo_image is not None:
            tk.Label(brand, image=self._sidebar_logo_image, bg=self.colors["sidebar"], borderwidth=0).grid(
                row=0, column=0, pady=(0, 8)
            )
        tk.Label(
            brand,
            text="SciPlot",
            bg=self.colors["sidebar"],
            fg="#ffffff",
            font=("Microsoft YaHei UI", 15, "bold"),
        ).grid(row=1, column=0)
        tk.Label(
            brand,
            text=f"v{APP_VERSION}",
            bg=self.colors["sidebar"],
            fg="#9fb5d9",
            font=("Microsoft YaHei UI", 8),
        ).grid(row=2, column=0, pady=(2, 0))

        nav_items = [
            ("home", "首頁"),
            ("data", "數據"),
            ("plot", "繪圖"),
            ("template", "模板"),
            ("export", "導出"),
            ("settings", "設置"),
            ("help", "幫助"),
        ]
        for row, (key, label) in enumerate(nav_items, start=1):
            self._sidebar_button(sidebar, key, label).grid(row=row, column=0, sticky="ew", padx=10, pady=4)
        tk.Label(sidebar, text="Ready", bg=self.colors["sidebar"], fg="#b9c7df", font=("Microsoft YaHei UI", 9)).grid(
            row=99, column=0, sticky="sew", padx=12, pady=12
        )
        sidebar.rowconfigure(98, weight=1)

    def _sidebar_button(self, parent: tk.Frame, key: str, label: str) -> tk.Button:
        button = tk.Button(
            parent,
            text=label,
            anchor="w",
            bg=self.colors["sidebar"],
            fg="#dbeafe",
            activebackground=self.colors["sidebar_active"],
            activeforeground="#ffffff",
            relief="flat",
            borderwidth=0,
            padx=14,
            pady=12,
            font=("Microsoft YaHei UI", 11, "bold" if key == "home" else "normal"),
            command=lambda item=key: self.navigate(item),
        )
        self.nav_buttons[key] = button
        return button

    def _set_active_nav(self, key: str) -> None:
        for item, button in self.nav_buttons.items():
            active = item == key
            button.configure(
                bg=self.colors["sidebar_active"] if active else self.colors["sidebar"],
                fg="#ffffff" if active else "#dbeafe",
                font=("Microsoft YaHei UI", 11, "bold" if active else "normal"),
            )

    def navigate(self, key: str) -> None:
        if key == "home":
            self.show_page("home", "首頁", "導入數據、創建圖表、套用模板，然後導出論文可用圖片。")
            self._set_active_nav("home")
            self.refresh_home_lists()
            return
        if key == "help":
            self.show_about()
            return
        self.show_page("workbench", "圖表工作區", "左側選數據與圖表，中間預覽，右側調整樣式與模板。")
        control_map = {"data": 0, "plot": 1, "settings": 2, "template": 3, "export": 1}
        workspace_map = {"data": 1, "plot": 0, "settings": 0, "template": 0, "export": 0}
        self._select_controls_tab(control_map.get(key, 1))
        self._select_workspace_tab(workspace_map.get(key, 0))
        self._set_active_nav(key if key != "export" else "plot")
        if key == "export":
            self.open_export_dialog()

    def show_page(self, page_key: str, title: str, subtitle: str) -> None:
        self.pages[page_key].tkraise()
        self.header_title_var.set(title)
        self.header_subtitle_var.set(subtitle)

    def _select_controls_tab(self, index: int) -> None:
        if index < 2 and hasattr(self, "controls_notebook"):
            self.controls_notebook.select(index)
        elif index >= 2 and hasattr(self, "side_settings_notebook"):
            self.side_settings_notebook.select(index - 2)

    def _select_workspace_tab(self, index: int) -> None:
        if hasattr(self, "workspace_notebook"):
            self.workspace_notebook.select(index)

    def _build_home_page(self, parent: ttk.Frame) -> None:
        parent.columnconfigure((0, 1), weight=1, uniform="homecards")
        parent.rowconfigure(3, weight=1)

        actions = [
            ("導入數據", "CSV、TSV、TXT、Excel", "載入數據", self.open_data),
            ("示例數據", "快速載入內置測試數據", "載入示例", self.load_sample_data),
            ("新建圖表", "從示例或當前數據開始", "開始繪圖", lambda: self.navigate("plot")),
            ("高級圖表", "3D、密度、極坐標、統計分布", "選擇圖表", lambda: self.navigate("plot")),
            ("導入模板", "使用共享的 JSON 模板", "導入模板", self.import_template),
            ("檢查更新", "從 GitHub 下載最新安裝包", "檢查更新", self.check_for_updates),
        ]
        for index, (title, desc, action, command) in enumerate(actions):
            row = index // 2
            col = index % 2
            card = self._home_action_card(parent, title, desc, action, command)
            card.grid(row=row, column=col, sticky="nsew", padx=(0 if col == 0 else 8, 0 if col == 1 else 8), pady=(0, 14))

        recent_projects = self._home_list_panel(parent, "最近項目")
        recent_projects.grid(row=3, column=0, sticky="nsew", padx=(0, 8), pady=(2, 0))
        self.recent_projects_frame = recent_projects.body

        recent_files = self._home_list_panel(parent, "最近文件")
        recent_files.grid(row=3, column=1, sticky="nsew", padx=(8, 0), pady=(2, 0))
        self.recent_files_frame = recent_files.body

    def _home_action_card(self, parent: ttk.Frame, title: str, description: str, action: str, command: Any) -> tk.Frame:
        card = tk.Frame(parent, bg=self.colors["surface"], highlightthickness=1, highlightbackground=self.colors["border"])
        card.configure(width=260, height=158)
        card.grid_propagate(False)
        card.columnconfigure(0, weight=1)
        tk.Label(card, text=title, bg=self.colors["surface"], fg=self.colors["text"], font=("Microsoft YaHei UI", 13, "bold")).grid(
            row=0, column=0, sticky="w", padx=20, pady=(20, 5)
        )
        tk.Label(
            card,
            text=description,
            bg=self.colors["surface"],
            fg=self.colors["muted"],
            font=("Microsoft YaHei UI", 10),
            wraplength=230,
            justify="left",
        ).grid(
            row=1, column=0, sticky="w", padx=20
        )
        button = tk.Button(
            card,
            text=action,
            command=command,
            bg=self.colors["primary"],
            fg="#ffffff",
            activebackground=self.colors["primary_dark"],
            activeforeground="#ffffff",
            relief="flat",
            borderwidth=0,
            cursor="hand2",
            font=("Microsoft YaHei UI", 10, "bold"),
            pady=8,
        )
        button.grid(row=2, column=0, sticky="ew", padx=20, pady=(18, 18))
        return card

    def _home_list_panel(self, parent: ttk.Frame, title: str) -> tk.Frame:
        panel = tk.Frame(parent, bg=self.colors["surface"], highlightthickness=1, highlightbackground=self.colors["border"])
        panel.columnconfigure(0, weight=1)
        tk.Label(panel, text=title, bg=self.colors["surface"], fg=self.colors["text"], font=("Microsoft YaHei UI", 10, "bold")).grid(
            row=0, column=0, sticky="w", padx=16, pady=(14, 8)
        )
        body = tk.Frame(panel, bg=self.colors["surface"])
        body.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        body.columnconfigure(0, weight=1)
        panel.body = body  # type: ignore[attr-defined]
        return panel

    def _build_workbench_page(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        quickbar = ttk.Frame(parent, style="App.TFrame")
        quickbar.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        quickbar.columnconfigure(8, weight=1)
        ttk.Button(quickbar, text="載入數據", style="Tool.TButton", command=self.open_data).grid(row=0, column=0, padx=(0, 6))
        ttk.Button(quickbar, text="示例數據", style="Tool.TButton", command=self.load_sample_data).grid(row=0, column=1, padx=6)
        ttk.Button(quickbar, text="生成圖表", style="Accent.TButton", command=self.render_plot).grid(row=0, column=2, padx=6)
        ttk.Button(quickbar, text="打開項目", style="Tool.TButton", command=self.load_project).grid(row=0, column=3, padx=6)
        ttk.Button(quickbar, text="保存項目", style="Tool.TButton", command=self.save_project).grid(row=0, column=4, padx=6)
        ttk.Button(quickbar, text="導出", style="Tool.TButton", command=self.open_export_dialog).grid(row=0, column=5, padx=6)

        paned = ttk.PanedWindow(parent, orient="horizontal")
        paned.grid(row=1, column=0, sticky="nsew")

        left = ttk.Frame(paned, width=292, style="Surface.TFrame")
        center = ttk.Frame(paned, style="Surface.TFrame")
        right = ttk.Frame(paned, width=276, style="Surface.TFrame")
        paned.add(left, weight=0)
        paned.add(center, weight=1)
        paned.add(right, weight=0)

        left.columnconfigure(0, weight=1)
        left.rowconfigure(0, weight=1)
        self._build_controls(left)

        center.columnconfigure(0, weight=1)
        center.rowconfigure(0, weight=1)
        self._build_workspace(center)

        right.columnconfigure(0, weight=1)
        right.rowconfigure(0, weight=1)
        self._build_side_settings(right)

    def refresh_home_lists(self) -> None:
        if not hasattr(self, "recent_projects_frame"):
            return
        for frame in (self.recent_projects_frame, self.recent_files_frame):
            for child in frame.winfo_children():
                child.destroy()

        projects = sorted(USER_DATA_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:5]
        if projects:
            for row, path in enumerate(projects):
                self._home_list_item(self.recent_projects_frame, path.name, str(path), row)
        else:
            self._home_list_item(self.recent_projects_frame, "暫無項目", "保存項目後會出現在這裡", 0)

        files: list[Path] = []
        seen_file_names: set[str] = set()
        if self.data_source:
            source_path = Path(self.data_source)
            files.append(source_path)
            seen_file_names.add(source_path.name.lower())
        sample_path = APP_HOME / "sample_data" / "example_measurements.csv"
        if sample_path.exists() and sample_path.name.lower() not in seen_file_names:
            files.append(sample_path)
            seen_file_names.add(sample_path.name.lower())
        for path in sorted(EXPORT_DIR.glob("*.*"), key=lambda p: p.stat().st_mtime, reverse=True)[:4]:
            if path.name.lower() not in seen_file_names:
                files.append(path)
                seen_file_names.add(path.name.lower())
        if files:
            for row, path in enumerate(files[:5]):
                self._home_list_item(self.recent_files_frame, path.name, str(path), row)
        else:
            self._home_list_item(self.recent_files_frame, "暫無文件", "導入或導出後會出現在這裡", 0)

    def _home_list_item(self, parent: tk.Frame, title: str, detail: str, row: int) -> None:
        item = tk.Frame(parent, bg=self.colors["surface"])
        item.grid(row=row, column=0, sticky="ew", pady=4)
        item.columnconfigure(0, weight=1)
        tk.Label(item, text=title, bg=self.colors["surface"], fg=self.colors["text"], font=("Microsoft YaHei UI", 9, "bold")).grid(
            row=0, column=0, sticky="w"
        )
        tk.Label(
            item,
            text=detail,
            bg=self.colors["surface"],
            fg=self.colors["muted"],
            font=("Microsoft YaHei UI", 8),
            anchor="w",
            wraplength=420,
        ).grid(row=1, column=0, sticky="ew", pady=(2, 0))

    def _build_menu(self) -> None:
        menu = tk.Menu(self)
        file_menu = tk.Menu(menu, tearoff=0)
        file_menu.add_command(label="載入數據", command=self.open_data)
        file_menu.add_command(label="保存項目", command=self.save_project)
        file_menu.add_command(label="載入項目", command=self.load_project)
        file_menu.add_separator()
        file_menu.add_command(label="退出", command=self.destroy)
        menu.add_cascade(label="文件", menu=file_menu)

        export_menu = tk.Menu(menu, tearoff=0)
        export_menu.add_command(label="PNG", command=lambda: self.export_figure("png"))
        export_menu.add_command(label="SVG", command=lambda: self.export_figure("svg"))
        export_menu.add_command(label="PDF", command=lambda: self.export_figure("pdf"))
        menu.add_cascade(label="導出", menu=export_menu)

        help_menu = tk.Menu(menu, tearoff=0)
        help_menu.add_command(label="檢查更新", command=self.check_for_updates)
        help_menu.add_separator()
        help_menu.add_command(label="關於", command=self.show_about)
        menu.add_cascade(label="幫助", menu=help_menu)
        self.configure(menu=menu)

    def _build_controls(self, parent: ttk.Frame) -> None:
        notebook = ttk.Notebook(parent)
        notebook.grid(row=0, column=0, sticky="nsew")
        self.controls_notebook = notebook

        data_tab = ScrollFrame(notebook, width=286)
        plot_tab = ScrollFrame(notebook, width=286)

        notebook.add(data_tab, text="數據")
        notebook.add(plot_tab, text="繪圖")

        self._build_data_tab(data_tab.inner)
        self._build_plot_tab(plot_tab.inner)

    def _build_side_settings(self, parent: ttk.Frame) -> None:
        notebook = ttk.Notebook(parent)
        notebook.grid(row=0, column=0, sticky="nsew")
        self.side_settings_notebook = notebook

        style_tab = ScrollFrame(notebook, width=270)
        template_tab = ScrollFrame(notebook, width=270)
        notebook.add(style_tab, text="樣式")
        notebook.add(template_tab, text="模板")

        self._build_style_tab(style_tab.inner)
        self._build_template_tab(template_tab.inner)

    def _build_data_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        ttk.Label(parent, text="數據來源", style="Title.TLabel").grid(row=0, column=0, sticky="w", padx=12, pady=(12, 6))
        ttk.Button(parent, text="載入 CSV / Excel", command=self.open_data).grid(row=1, column=0, sticky="ew", padx=12, pady=4)
        ttk.Button(parent, text="使用內置示例數據", command=self.load_sample_data).grid(row=2, column=0, sticky="ew", padx=12, pady=4)

        self.source_var = tk.StringVar(value="尚未載入")
        ttk.Label(parent, textvariable=self.source_var, wraplength=320, foreground="#4b5563").grid(
            row=3, column=0, sticky="ew", padx=12, pady=(8, 12)
        )

        ttk.Label(parent, text="數據要求", style="Title.TLabel").grid(row=4, column=0, sticky="w", padx=12, pady=(10, 6))
        requirement = (
            "第一行需為欄位名稱。數值欄會自動識別；CSV 支援逗號、Tab、分號等常見分隔符。"
        )
        ttk.Label(parent, text=requirement, wraplength=320, foreground="#374151").grid(row=5, column=0, sticky="ew", padx=12, pady=4)

        self.data_stats_var = tk.StringVar(value="行數：0｜欄數：0")
        ttk.Label(parent, textvariable=self.data_stats_var, foreground="#111827").grid(row=6, column=0, sticky="w", padx=12, pady=(10, 4))

    def _build_plot_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        row = 0
        ttk.Label(parent, text="圖表設置", style="Title.TLabel").grid(row=row, column=0, sticky="w", padx=12, pady=(12, 6))
        row += 1

        self.chart_type_var = tk.StringVar(value=self.current_settings.chart_type)
        self._combo(parent, "圖表類型", self.chart_type_var, list(CHART_TYPES.keys()), row)
        row += 2

        self.x_col_var = tk.StringVar()
        self.x_combo = self._combo(parent, "X 軸欄位", self.x_col_var, [], row)
        row += 2

        ttk.Label(parent, text="Y 軸欄位（可多選）").grid(row=row, column=0, sticky="w", padx=12, pady=(8, 2))
        row += 1
        self.y_listbox = tk.Listbox(parent, height=8, selectmode="extended", exportselection=False)
        self.y_listbox.grid(row=row, column=0, sticky="ew", padx=12, pady=4)
        row += 1

        self.error_col_var = tk.StringVar()
        self.error_combo = self._combo(parent, "誤差欄位", self.error_col_var, [], row)
        row += 2

        self.z_col_var = tk.StringVar()
        self.z_combo = self._combo(parent, "Z 軸 / 強度欄位", self.z_col_var, [], row)
        row += 2

        self.size_col_var = tk.StringVar()
        self.size_combo = self._combo(parent, "點大小欄位", self.size_col_var, [], row)
        row += 2

        self.color_col_var = tk.StringVar()
        self.color_combo = self._combo(parent, "顏色映射欄位", self.color_col_var, [], row)
        row += 2

        self.group_col_var = tk.StringVar()
        self.group_combo = self._combo(parent, "分組欄位", self.group_col_var, [], row)
        row += 2

        self.title_var = tk.StringVar()
        self._entry(parent, "標題", self.title_var, row)
        row += 2
        self.xlabel_var = tk.StringVar()
        self._entry(parent, "X 軸標籤", self.xlabel_var, row)
        row += 2
        self.ylabel_var = tk.StringVar()
        self._entry(parent, "Y 軸標籤", self.ylabel_var, row)
        row += 2
        self.zlabel_var = tk.StringVar()
        self._entry(parent, "Z 軸標籤", self.zlabel_var, row)
        row += 2

        ttk.Button(parent, text="生成 / 更新圖表", style="Accent.TButton", command=self.render_plot).grid(
            row=row, column=0, sticky="ew", padx=12, pady=(12, 8)
        )

    def _build_style_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        row = 0
        ttk.Label(parent, text="出版與樣式", style="Title.TLabel").grid(row=row, column=0, sticky="w", padx=12, pady=(12, 6))
        row += 1

        self.width_var = tk.DoubleVar(value=self.current_settings.width)
        self._spin(parent, "寬度（英寸）", self.width_var, 2.0, 16.0, 0.1, row)
        row += 2
        self.height_var = tk.DoubleVar(value=self.current_settings.height)
        self._spin(parent, "高度（英寸）", self.height_var, 2.0, 12.0, 0.1, row)
        row += 2
        self.dpi_var = tk.IntVar(value=self.current_settings.dpi)
        self._spin(parent, "DPI", self.dpi_var, 72, 1200, 10, row)
        row += 2
        self.font_size_var = tk.IntVar(value=self.current_settings.font_size)
        self._spin(parent, "字體大小", self.font_size_var, 6, 28, 1, row)
        row += 2
        self.line_width_var = tk.DoubleVar(value=self.current_settings.line_width)
        self._spin(parent, "線寬", self.line_width_var, 0.2, 8.0, 0.1, row)
        row += 2
        self.marker_size_var = tk.DoubleVar(value=self.current_settings.marker_size)
        self._spin(parent, "標記大小", self.marker_size_var, 0.0, 18.0, 0.5, row)
        row += 2

        self.bins_var = tk.IntVar(value=self.current_settings.bins)
        self._spin(parent, "分箱 / 網格密度", self.bins_var, 5, 120, 1, row)
        row += 2

        self.elev_var = tk.IntVar(value=self.current_settings.elev)
        self._spin(parent, "3D 仰角", self.elev_var, -90, 90, 1, row)
        row += 2

        self.azim_var = tk.IntVar(value=self.current_settings.azim)
        self._spin(parent, "3D 方位角", self.azim_var, -180, 180, 1, row)
        row += 2

        self.marker_var = tk.StringVar(value=self.current_settings.marker)
        self._combo(parent, "標記形狀", self.marker_var, ["o", "s", "^", "D", "x", "+", ".", "None"], row)
        row += 2
        self.palette_var = tk.StringVar(value=self.current_settings.palette)
        self._combo(parent, "配色", self.palette_var, list(PALETTES.keys()), row)
        row += 2

        self.grid_var = tk.BooleanVar(value=self.current_settings.grid)
        ttk.Checkbutton(parent, text="顯示網格", variable=self.grid_var).grid(row=row, column=0, sticky="w", padx=12, pady=4)
        row += 1
        self.legend_var = tk.BooleanVar(value=self.current_settings.legend)
        ttk.Checkbutton(parent, text="顯示圖例", variable=self.legend_var).grid(row=row, column=0, sticky="w", padx=12, pady=4)
        row += 1
        self.tight_layout_var = tk.BooleanVar(value=self.current_settings.tight_layout)
        ttk.Checkbutton(parent, text="自動緊湊排版", variable=self.tight_layout_var).grid(row=row, column=0, sticky="w", padx=12, pady=4)
        row += 1

        ttk.Label(parent, text="標籤與留白微調", style="Title.TLabel").grid(row=row, column=0, sticky="w", padx=12, pady=(16, 6))
        row += 1
        self.title_pad_var = tk.IntVar(value=self.current_settings.title_pad)
        self._spin(parent, "標題距離", self.title_pad_var, 0, 80, 1, row)
        row += 2
        self.axis_label_pad_var = tk.IntVar(value=self.current_settings.axis_label_pad)
        self._spin(parent, "軸標籤距離", self.axis_label_pad_var, 0, 60, 1, row)
        row += 2
        self.tick_label_pad_var = tk.IntVar(value=self.current_settings.tick_label_pad)
        self._spin(parent, "刻度文字距離", self.tick_label_pad_var, 0, 40, 1, row)
        row += 2
        self.x_tick_rotation_var = tk.IntVar(value=self.current_settings.x_tick_rotation)
        self._spin(parent, "X 刻度旋轉", self.x_tick_rotation_var, -90, 90, 5, row)
        row += 2
        self.legend_position_var = tk.StringVar(value=self.current_settings.legend_position)
        self._combo(parent, "圖例位置", self.legend_position_var, ["自動", "右上", "右側", "底部", "左上", "無"], row)
        row += 2
        self.margin_left_var = tk.DoubleVar(value=self.current_settings.margin_left)
        self._spin(parent, "左留白（0=自動）", self.margin_left_var, 0.0, 0.45, 0.01, row)
        row += 2
        self.margin_right_var = tk.DoubleVar(value=self.current_settings.margin_right)
        self._spin(parent, "右留白（0=自動）", self.margin_right_var, 0.0, 0.45, 0.01, row)
        row += 2
        self.margin_top_var = tk.DoubleVar(value=self.current_settings.margin_top)
        self._spin(parent, "上留白（0=自動）", self.margin_top_var, 0.0, 0.45, 0.01, row)
        row += 2
        self.margin_bottom_var = tk.DoubleVar(value=self.current_settings.margin_bottom)
        self._spin(parent, "下留白（0=自動）", self.margin_bottom_var, 0.0, 0.45, 0.01, row)

    def _build_template_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        row = 0
        ttk.Label(parent, text="免費模板", style="Title.TLabel").grid(row=row, column=0, sticky="w", padx=12, pady=(12, 6))
        row += 1
        self.template_var = tk.StringVar(value="SciPlot Classic")
        self.template_combo = self._combo(parent, "模板", self.template_var, self._template_names(), row)
        row += 2
        ttk.Button(parent, text="套用模板", command=self.apply_selected_template).grid(row=row, column=0, sticky="ew", padx=12, pady=4)
        row += 1
        ttk.Button(parent, text="保存當前樣式為模板", command=self.save_current_template).grid(row=row, column=0, sticky="ew", padx=12, pady=4)
        row += 1
        ttk.Button(parent, text="導入模板 JSON", command=self.import_template).grid(row=row, column=0, sticky="ew", padx=12, pady=4)
        row += 1
        ttk.Button(parent, text="導出當前模板 JSON", command=self.export_template).grid(row=row, column=0, sticky="ew", padx=12, pady=4)
        row += 1
        text = "本版本不包含模板市場、付費購買、賬號或商業授權流程。模板僅用於本地免費共享。"
        ttk.Label(parent, text=text, wraplength=320, foreground="#374151").grid(row=row, column=0, sticky="ew", padx=12, pady=(12, 4))

    def _build_workspace(self, parent: ttk.Frame) -> None:
        notebook = ttk.Notebook(parent)
        notebook.grid(row=0, column=0, sticky="nsew")
        self.workspace_notebook = notebook

        plot_frame = ttk.Frame(notebook, style="Surface.TFrame")
        table_frame = ttk.Frame(notebook, style="Surface.TFrame")
        notebook.add(plot_frame, text="圖表")
        notebook.add(table_frame, text="數據預覽")

        plot_frame.columnconfigure(0, weight=1)
        plot_frame.rowconfigure(0, weight=1)
        self.plot_container = ttk.Frame(plot_frame)
        self.plot_container.grid(row=0, column=0, sticky="nsew")

        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)
        self.table = ttk.Treeview(table_frame, show="headings")
        ybar = ttk.Scrollbar(table_frame, orient="vertical", command=self.table.yview)
        xbar = ttk.Scrollbar(table_frame, orient="horizontal", command=self.table.xview)
        self.table.configure(yscrollcommand=ybar.set, xscrollcommand=xbar.set)
        self.table.grid(row=0, column=0, sticky="nsew")
        ybar.grid(row=0, column=1, sticky="ns")
        xbar.grid(row=1, column=0, sticky="ew")

    def _combo(self, parent: ttk.Frame, label: str, variable: tk.StringVar, values: list[str], row: int) -> ttk.Combobox:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=12, pady=(8, 2))
        combo = ttk.Combobox(parent, textvariable=variable, values=values, state="readonly")
        combo.grid(row=row + 1, column=0, sticky="ew", padx=12, pady=4)
        return combo

    def _entry(self, parent: ttk.Frame, label: str, variable: tk.StringVar, row: int) -> ttk.Entry:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=12, pady=(8, 2))
        entry = ttk.Entry(parent, textvariable=variable)
        entry.grid(row=row + 1, column=0, sticky="ew", padx=12, pady=4)
        return entry

    def _spin(
        self,
        parent: ttk.Frame,
        label: str,
        variable: tk.Variable,
        from_: float,
        to: float,
        increment: float,
        row: int,
    ) -> ttk.Spinbox:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=12, pady=(8, 2))
        spin = ttk.Spinbox(parent, textvariable=variable, from_=from_, to=to, increment=increment)
        spin.grid(row=row + 1, column=0, sticky="ew", padx=12, pady=4)
        return spin

    def _template_names(self) -> list[str]:
        names = list(BUILTIN_TEMPLATES.keys())
        for path in sorted(TEMPLATE_DIR.glob("*.json")):
            if path.stem not in names:
                names.append(path.stem)
        return names

    def _normalize_chart_type(self, value: Any) -> str:
        if value in CHART_TYPES:
            return str(value)
        if isinstance(value, str):
            for label, chart_key in CHART_TYPES.items():
                if value == chart_key:
                    return label
        return self.current_settings.chart_type

    def _read_template_file(self, path: Path) -> dict[str, Any]:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("Template JSON must contain an object.")
        return data

    def _template_number(self, template: dict[str, Any], key: str, variable: tk.Variable, cast: Any) -> Any:
        fallback = variable.get()
        try:
            return cast(template.get(key, fallback))
        except (TypeError, ValueError, tk.TclError):
            return fallback

    def _template_bool(self, template: dict[str, Any], key: str, variable: tk.Variable) -> bool:
        value = template.get(key, variable.get())
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "y", "on"}
        return bool(value)

    def _load_last_session(self) -> None:
        if not STATE_PATH.exists():
            self.set_status("就緒。載入數據後可生成圖表。")
            return
        try:
            payload = json.loads(STATE_PATH.read_text(encoding="utf-8"))
            records = payload.get("records") or []
            columns = payload.get("columns") or None
            source = payload.get("data_source", "")
            if records:
                self.df = pd.DataFrame(records, columns=columns)
                self.data_source = source
            elif source and Path(source).exists():
                self.df = self._read_data_file(Path(source))
                self.data_source = source
            else:
                self.set_status("就緒。載入數據後可生成圖表。")
                return
            self.source_var.set(self.data_source or "上次會話")
            self.refresh_after_data_load()
            self.restore_settings(payload.get("settings", {}))
            self.render_plot(silent=True, persist=False)
            if self.figure is not None:
                self.navigate("plot")
                self.set_status("已恢復上次生成的圖表。")
        except Exception:
            self.set_status("未能恢復上次圖表，請重新載入數據。")

    def load_sample_data(self, silent: bool = False) -> None:
        sample_path = APP_HOME / "sample_data" / "example_measurements.csv"
        if not sample_path.exists():
            sample_path = SAMPLE_DIR / "example_measurements.csv"
        if not sample_path.exists():
            if not silent:
                messagebox.showwarning("示例數據缺失", "未找到 sample_data/example_measurements.csv。")
            return
        try:
            self.df = pd.read_csv(sample_path)
            self.data_source = str(sample_path)
            self.source_var.set(str(sample_path))
            self.refresh_after_data_load()
            self.set_status(f"已載入示例數據：{sample_path.name}")
            if not silent:
                self.navigate("plot")
        except Exception as exc:
            if not silent:
                messagebox.showerror("載入失敗", f"無法載入示例數據：\n{exc}")

    def open_data(self) -> None:
        path = filedialog.askopenfilename(
            title="選擇數據文件",
            initialdir=str(APP_HOME),
            filetypes=[
                ("數據文件", "*.csv *.tsv *.txt *.xlsx *.xls"),
                ("CSV", "*.csv"),
                ("Excel", "*.xlsx *.xls"),
                ("所有文件", "*.*"),
            ],
        )
        if not path:
            return
        try:
            self.df = self._read_data_file(Path(path))
            self.data_source = path
            self.source_var.set(path)
            self.refresh_after_data_load()
            self.navigate("plot")
            self.set_status(f"已載入數據：{Path(path).name}。請點擊「生成圖表」。")
        except Exception as exc:
            messagebox.showerror("載入失敗", f"無法讀取數據文件：\n{exc}")

    def _read_data_file(self, path: Path) -> pd.DataFrame:
        suffix = path.suffix.lower()
        if suffix in {".xlsx", ".xls"}:
            df = pd.read_excel(path)
        elif suffix == ".tsv":
            df = self._read_text_table(path, sep="\t")
        elif suffix == ".csv":
            df = self._read_text_table(path, sep=",", allow_sniff=True)
        else:
            df = self._read_text_table(path, sep=None, allow_sniff=True)
        if df.empty or len(df.columns) == 0:
            raise ValueError("文件沒有可用數據。")
        return df

    def _read_text_table(self, path: Path, sep: str | None, allow_sniff: bool = False) -> pd.DataFrame:
        last_error: Exception | None = None
        encodings = ("utf-8-sig", "utf-8", "gb18030", "cp1252")
        for encoding in encodings:
            try:
                if sep is None:
                    return pd.read_csv(path, sep=None, engine="python", encoding=encoding)
                df = pd.read_csv(path, sep=sep, encoding=encoding)
                if allow_sniff and len(df.columns) <= 1:
                    sniffed = pd.read_csv(path, sep=None, engine="python", encoding=encoding)
                    if len(sniffed.columns) > len(df.columns):
                        return sniffed
                return df
            except UnicodeDecodeError as exc:
                last_error = exc
                continue
            except pd.errors.ParserError as exc:
                last_error = exc
                if allow_sniff:
                    try:
                        return pd.read_csv(path, sep=None, engine="python", encoding=encoding)
                    except Exception as sniff_exc:
                        last_error = sniff_exc
                continue
        if last_error is not None:
            raise last_error
        raise ValueError("文件無法讀取。")

    def refresh_after_data_load(self) -> None:
        self._numeric_cache.clear()
        self.df.columns = self._make_unique_columns([str(col).strip() or "Column" for col in self.df.columns])
        self.data_stats_var.set(f"行數：{len(self.df):,}｜欄數：{len(self.df.columns):,}")
        self.update_column_controls()
        self.update_preview_table()
        self.refresh_home_lists()

    def _make_unique_columns(self, columns: list[str]) -> list[str]:
        seen: dict[str, int] = {}
        unique: list[str] = []
        for col in columns:
            count = seen.get(col, 0)
            seen[col] = count + 1
            unique.append(col if count == 0 else f"{col}_{count + 1}")
        return unique

    def update_column_controls(self) -> None:
        columns = [""] + list(self.df.columns)
        numeric_cols = self.numeric_columns()
        self.x_combo.configure(values=columns)
        self.error_combo.configure(values=[""] + numeric_cols)
        self.z_combo.configure(values=[""] + numeric_cols)
        self.size_combo.configure(values=[""] + numeric_cols)
        self.color_combo.configure(values=[""] + numeric_cols)
        self.group_combo.configure(values=columns)
        if not self.x_col_var.get() and self.df.columns.size:
            self.x_col_var.set(str(self.df.columns[0]))
        if not self.z_col_var.get() and len(numeric_cols) > 2:
            self.z_col_var.set(numeric_cols[2])

        self.y_listbox.delete(0, "end")
        for col in numeric_cols:
            self.y_listbox.insert("end", col)
        if numeric_cols:
            self._select_y_columns(numeric_cols[1:2] if len(numeric_cols) > 1 else numeric_cols[:1])

    def update_preview_table(self) -> None:
        self.table.delete(*self.table.get_children())
        columns = list(self.df.columns[:80])
        self.table["columns"] = columns
        for col in columns:
            self.table.heading(col, text=col)
            self.table.column(col, width=120, stretch=False)
        preview = self.df.head(200).replace({np.nan: ""})
        for _, row in preview.iterrows():
            values = [self._format_cell(row.get(col, "")) for col in columns]
            self.table.insert("", "end", values=values)

    def _format_cell(self, value: Any) -> str:
        if isinstance(value, float):
            return f"{value:.6g}"
        return str(value)

    def numeric_columns(self) -> list[str]:
        cols = []
        for col in self.df.columns:
            series = self._numeric_series(str(col))
            if series.notna().sum() > 0:
                cols.append(str(col))
        return cols

    def selected_y_columns(self) -> list[str]:
        return [self.y_listbox.get(index) for index in self.y_listbox.curselection()]

    def _select_y_columns(self, cols: list[str]) -> None:
        wanted = set(cols)
        self.y_listbox.selection_clear(0, "end")
        for index in range(self.y_listbox.size()):
            if self.y_listbox.get(index) in wanted:
                self.y_listbox.selection_set(index)

    def collect_settings(self) -> PlotSettings:
        marker = self.marker_var.get()
        if marker == "None":
            marker = ""
        return PlotSettings(
            chart_type=self.chart_type_var.get(),
            x_col=self.x_col_var.get(),
            y_cols=self.selected_y_columns(),
            z_col=self.z_col_var.get(),
            error_col=self.error_col_var.get(),
            group_col=self.group_col_var.get(),
            size_col=self.size_col_var.get(),
            color_col=self.color_col_var.get(),
            title=self.title_var.get(),
            xlabel=self.xlabel_var.get(),
            ylabel=self.ylabel_var.get(),
            zlabel=self.zlabel_var.get(),
            width=self._float_var(self.width_var, 7.2, 2.0, 16.0),
            height=self._float_var(self.height_var, 4.2, 2.0, 12.0),
            dpi=self._int_var(self.dpi_var, 300, 72, 1200),
            font_size=self._int_var(self.font_size_var, 10, 6, 28),
            line_width=self._float_var(self.line_width_var, 1.8, 0.2, 8.0),
            marker_size=self._float_var(self.marker_size_var, 5.0, 0.0, 18.0),
            marker=marker,
            palette=self.palette_var.get(),
            grid=bool(self.grid_var.get()),
            legend=bool(self.legend_var.get()),
            tight_layout=bool(self.tight_layout_var.get()),
            title_pad=self._int_var(self.title_pad_var, 14, 0, 80),
            axis_label_pad=self._int_var(self.axis_label_pad_var, 8, 0, 60),
            tick_label_pad=self._int_var(self.tick_label_pad_var, 4, 0, 40),
            x_tick_rotation=self._int_var(self.x_tick_rotation_var, 0, -90, 90),
            legend_position=self.legend_position_var.get(),
            margin_left=self._float_var(self.margin_left_var, 0.0, 0.0, 0.45),
            margin_right=self._float_var(self.margin_right_var, 0.0, 0.0, 0.45),
            margin_top=self._float_var(self.margin_top_var, 0.0, 0.0, 0.45),
            margin_bottom=self._float_var(self.margin_bottom_var, 0.0, 0.0, 0.45),
            bins=self._int_var(self.bins_var, 30, 5, 120),
            elev=self._int_var(self.elev_var, 28, -90, 90),
            azim=self._int_var(self.azim_var, -55, -180, 180),
        )

    def _float_var(self, variable: tk.Variable, fallback: float, minimum: float, maximum: float) -> float:
        try:
            value = float(variable.get())
        except (tk.TclError, TypeError, ValueError):
            value = fallback
            variable.set(value)
        value = max(minimum, min(maximum, value))
        variable.set(value)
        return value

    def _int_var(self, variable: tk.Variable, fallback: int, minimum: int, maximum: int) -> int:
        try:
            value = int(float(variable.get()))
        except (tk.TclError, TypeError, ValueError):
            value = fallback
            variable.set(value)
        value = max(minimum, min(maximum, value))
        variable.set(value)
        return value

    def render_plot(self, silent: bool = False, persist: bool | None = None) -> None:
        if self.df.empty:
            if not silent:
                messagebox.showwarning("沒有數據", "請先載入 CSV 或 Excel 數據。")
            return
        if persist is None:
            persist = not silent
        settings = self.collect_settings()
        chart_key = CHART_TYPES.get(settings.chart_type, "line")
        no_x_required = {"histogram", "density", "ecdf", "boxplot", "violin", "heatmap", "radar", "pie", "donut"}
        y_optional = {"heatmap", "pie", "donut"}
        z_required = {"scatter3d", "line3d", "surface3d", "wireframe3d", "bar3d", "contour3d", "contour", "contourf"}
        if chart_key not in no_x_required and not settings.x_col:
            messagebox.showwarning("缺少 X 軸", "請選擇 X 軸欄位。")
            return
        if chart_key not in y_optional and not settings.y_cols:
            messagebox.showwarning("缺少 Y 軸", "請至少選擇一個 Y 軸欄位。")
            return
        if chart_key in z_required and not settings.z_col:
            messagebox.showwarning("缺少 Z 軸", "此圖表需要選擇 Z 軸 / 強度欄位。")
            return

        try:
            self.current_settings = settings
            preview_dpi = min(settings.dpi, 150)
            fig = self._create_plot_figure(settings, chart_key, preview_dpi)
            self._show_figure(fig)
            self.set_status(f"圖表已更新：{settings.chart_type}")
            if persist:
                self._save_last_session(settings)
        except Exception as exc:
            if not silent:
                messagebox.showerror("繪圖失敗", f"生成圖表時出錯：\n{exc}")

    def _create_plot_figure(self, settings: PlotSettings, chart_key: str, dpi: int) -> Figure:
        fig = Figure(figsize=(settings.width, settings.height), dpi=dpi)
        if chart_key in {"scatter3d", "line3d", "surface3d", "wireframe3d", "bar3d", "contour3d"}:
            ax = fig.add_subplot(111, projection="3d")
        elif chart_key in {"radar", "polar_line", "polar_scatter"}:
            ax = fig.add_subplot(111, projection="polar")
        else:
            ax = fig.add_subplot(111)
        fig.patch.set_facecolor("#ffffff")
        ax.set_facecolor("#ffffff")

        if hasattr(self, "figure_colorbar"):
            self.figure_colorbar = None
        colors = PALETTES.get(settings.palette, PALETTES["期刊藍灰"])
        rcParams["font.size"] = settings.font_size
        rcParams["pdf.fonttype"] = 42
        rcParams["ps.fonttype"] = 42
        self._plot_by_type(ax, chart_key, settings, colors)
        self._decorate_axes(ax, fig, settings, chart_key)
        return fig

    def _save_last_session(self, settings: PlotSettings) -> None:
        if self.df.empty:
            return
        source_path = Path(self.data_source) if self.data_source else None
        source_exists = bool(source_path and source_path.exists())
        include_records = len(self.df) <= MAX_SESSION_RECORDS or not source_exists
        payload = {
            "app": APP_NAME,
            "version": APP_VERSION,
            "data_source": self.data_source,
            "columns": list(self.df.columns),
            "row_count": len(self.df),
            "records": self.df.replace({np.nan: None}).to_dict(orient="records") if include_records else [],
            "settings": asdict(settings),
        }
        if source_exists and source_path is not None:
            stat = source_path.stat()
            payload["source_mtime_ns"] = stat.st_mtime_ns
            payload["source_size"] = stat.st_size
        try:
            temp_path = STATE_PATH.with_suffix(".tmp")
            temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            temp_path.replace(STATE_PATH)
        except OSError:
            self.set_status("圖表已生成，但未能保存上次會話。")

    def _plot_by_type(self, ax: Any, chart_key: str, settings: PlotSettings, colors: list[str]) -> None:
        if chart_key == "line":
            self._plot_xy(ax, settings, colors, mode="line")
        elif chart_key == "step":
            self._plot_xy(ax, settings, colors, mode="step")
        elif chart_key == "area":
            self._plot_area(ax, settings, colors, stacked=False)
        elif chart_key == "stacked_area":
            self._plot_area(ax, settings, colors, stacked=True)
        elif chart_key == "scatter":
            self._plot_xy(ax, settings, colors, mode="scatter")
        elif chart_key == "bubble":
            self._plot_bubble(ax, settings, colors)
        elif chart_key == "bar":
            self._plot_bar(ax, settings, colors)
        elif chart_key == "barh":
            self._plot_barh(ax, settings, colors)
        elif chart_key == "errorbar":
            self._plot_errorbar(ax, settings, colors)
        elif chart_key == "histogram":
            self._plot_histogram(ax, settings, colors)
        elif chart_key == "density":
            self._plot_density(ax, settings, colors)
        elif chart_key == "ecdf":
            self._plot_ecdf(ax, settings, colors)
        elif chart_key == "boxplot":
            self._plot_boxplot(ax, settings, colors)
        elif chart_key == "violin":
            self._plot_violin(ax, settings, colors)
        elif chart_key == "stem":
            self._plot_stem(ax, settings, colors)
        elif chart_key == "lollipop":
            self._plot_lollipop(ax, settings, colors)
        elif chart_key == "heatmap":
            self._plot_heatmap(ax, settings)
        elif chart_key == "hist2d":
            self._plot_hist2d(ax, settings)
        elif chart_key == "hexbin":
            self._plot_hexbin(ax, settings)
        elif chart_key in {"contour", "contourf"}:
            self._plot_contour(ax, settings, filled=chart_key == "contourf")
        elif chart_key == "radar":
            self._plot_radar(ax, settings, colors)
        elif chart_key == "polar_line":
            self._plot_polar(ax, settings, colors, mode="line")
        elif chart_key == "polar_scatter":
            self._plot_polar(ax, settings, colors, mode="scatter")
        elif chart_key in {"pie", "donut"}:
            self._plot_pie(ax, settings, colors, donut=chart_key == "donut")
        elif chart_key in {"scatter3d", "line3d", "surface3d", "wireframe3d", "bar3d", "contour3d"}:
            self._plot_3d(ax, settings, colors, chart_key)
        else:
            self._plot_xy(ax, settings, colors, mode="line")

    def _numeric_series(self, col: str) -> pd.Series:
        if col not in self._numeric_cache:
            self._numeric_cache[col] = pd.to_numeric(self.df[col], errors="coerce")
        return self._numeric_cache[col]

    def _numeric_frame(self, cols: list[str]) -> pd.DataFrame:
        return self.df[cols].apply(pd.to_numeric, errors="coerce").dropna()

    def _triangulation_frame(self, x_col: str, y_col: str, z_col: str) -> tuple[pd.DataFrame, mtri.Triangulation]:
        frame = self._numeric_frame([x_col, y_col, z_col])
        frame = frame.groupby([x_col, y_col], as_index=False)[z_col].mean()
        if len(frame) < 3:
            raise ValueError("等高線或曲面圖至少需要三個不同的有效 X/Y 數據點。")
        points = frame[[x_col, y_col]].to_numpy(dtype=float)
        if np.linalg.matrix_rank(points - points.mean(axis=0)) < 2:
            raise ValueError("等高線或曲面圖需要非共線的 X/Y 數據點。")
        try:
            triangulation = mtri.Triangulation(frame[x_col], frame[y_col])
        except (RuntimeError, ValueError) as exc:
            raise ValueError("等高線或曲面圖需要非重合且分布有效的 X/Y 數據點。") from exc
        return frame, triangulation

    def _scaled_sizes(self, settings: PlotSettings, default: float = 40.0) -> pd.Series | float:
        if not settings.size_col:
            return max(default, settings.marker_size**2)
        values = self._numeric_series(settings.size_col)
        minimum = values.min(skipna=True)
        maximum = values.max(skipna=True)
        if pd.isna(minimum) or pd.isna(maximum) or maximum == minimum:
            return pd.Series(default, index=values.index)
        return 25 + (values - minimum) / (maximum - minimum) * 220

    def _color_values(self, settings: PlotSettings) -> pd.Series | None:
        if not settings.color_col:
            return None
        values = self._numeric_series(settings.color_col)
        return values if values.notna().sum() else None

    def _add_colorbar(self, ax: Any, artist: Any, label: str = "") -> None:
        if hasattr(ax, "figure") and artist is not None:
            ax.figure.colorbar(artist, ax=ax, fraction=0.046, pad=0.04, label=label)

    def _plot_xy(self, ax: Any, settings: PlotSettings, colors: list[str], mode: str) -> None:
        x_raw = self.df[settings.x_col]
        x_numeric = pd.to_numeric(x_raw, errors="coerce")
        x = x_numeric if x_numeric.notna().sum() >= len(x_numeric) * 0.5 else x_raw.astype(str)

        if settings.group_col:
            grouped = self.df.groupby(settings.group_col, dropna=True)
            for group_index, (group_name, group_df) in enumerate(grouped):
                for y_index, y_col in enumerate(settings.y_cols or []):
                    color = colors[(group_index + y_index) % len(colors)]
                    x_values = group_df[settings.x_col]
                    x_num = pd.to_numeric(x_values, errors="coerce")
                    x_values = x_num if x_num.notna().sum() >= len(x_num) * 0.5 else x_values.astype(str)
                    y_values = pd.to_numeric(group_df[y_col], errors="coerce")
                    label = f"{group_name} - {y_col}"
                    if mode == "line":
                        ax.plot(
                            x_values,
                            y_values,
                            label=label,
                            color=color,
                            linewidth=settings.line_width,
                            marker=settings.marker or None,
                            markersize=settings.marker_size,
                        )
                    elif mode == "step":
                        ax.step(
                            x_values,
                            y_values,
                            label=label,
                            color=color,
                            linewidth=settings.line_width,
                            where="mid",
                        )
                    else:
                        ax.scatter(x_values, y_values, label=label, color=color, s=settings.marker_size**2)
            return

        for index, y_col in enumerate(settings.y_cols or []):
            y = self._numeric_series(y_col)
            color = colors[index % len(colors)]
            if mode == "line":
                ax.plot(
                    x,
                    y,
                    label=y_col,
                    color=color,
                    linewidth=settings.line_width,
                    marker=settings.marker or None,
                    markersize=settings.marker_size,
                )
            elif mode == "step":
                ax.step(x, y, label=y_col, color=color, linewidth=settings.line_width, where="mid")
            else:
                ax.scatter(x, y, label=y_col, color=color, s=settings.marker_size**2)

    def _plot_area(self, ax: Any, settings: PlotSettings, colors: list[str], stacked: bool) -> None:
        x = self.df[settings.x_col]
        y_cols = settings.y_cols or []
        y_data = [self._numeric_series(col).fillna(0).to_numpy() for col in y_cols]
        if stacked and len(y_data) > 1:
            ax.stackplot(x, y_data, labels=y_cols, colors=colors[: len(y_cols)], alpha=0.82)
            return
        for index, (y_col, y) in enumerate(zip(y_cols, y_data)):
            color = colors[index % len(colors)]
            ax.plot(x, y, label=y_col, color=color, linewidth=settings.line_width)
            ax.fill_between(x, y, alpha=0.22, color=color)

    def _plot_bubble(self, ax: Any, settings: PlotSettings, colors: list[str]) -> None:
        y_col = (settings.y_cols or [""])[0]
        frame = self._numeric_frame([settings.x_col, y_col] + ([settings.size_col] if settings.size_col else []) + ([settings.color_col] if settings.color_col else []))
        c = frame[settings.color_col] if settings.color_col and settings.color_col in frame else None
        sizes = self._scaled_sizes(settings)
        if isinstance(sizes, pd.Series):
            sizes = sizes.reindex(frame.index).fillna(40)
        scatter_kwargs = {"c": c, "cmap": "viridis"} if c is not None else {"color": colors[0]}
        artist = ax.scatter(
            frame[settings.x_col],
            frame[y_col],
            s=sizes,
            alpha=0.72,
            edgecolors="#ffffff",
            linewidths=0.6,
            label=y_col,
            **scatter_kwargs,
        )
        if c is not None:
            self._add_colorbar(ax, artist, settings.color_col)

    def _plot_bar(self, ax: Any, settings: PlotSettings, colors: list[str]) -> None:
        x = self.df[settings.x_col].astype(str)
        y_cols = settings.y_cols or []
        indices = np.arange(len(x))
        width = min(0.8 / max(len(y_cols), 1), 0.35)
        for idx, y_col in enumerate(y_cols):
            y = self._numeric_series(y_col)
            offset = (idx - (len(y_cols) - 1) / 2) * width
            ax.bar(indices + offset, y, width=width, label=y_col, color=colors[idx % len(colors)])
        ax.set_xticks(indices)
        ax.set_xticklabels(x, rotation=30, ha="right")

    def _plot_barh(self, ax: Any, settings: PlotSettings, colors: list[str]) -> None:
        labels = self.df[settings.x_col].astype(str)
        y_cols = settings.y_cols or []
        indices = np.arange(len(labels))
        height = min(0.8 / max(len(y_cols), 1), 0.35)
        for idx, y_col in enumerate(y_cols):
            values = self._numeric_series(y_col)
            offset = (idx - (len(y_cols) - 1) / 2) * height
            ax.barh(indices + offset, values, height=height, label=y_col, color=colors[idx % len(colors)])
        ax.set_yticks(indices)
        ax.set_yticklabels(labels)
        ax.invert_yaxis()

    def _plot_errorbar(self, ax: Any, settings: PlotSettings, colors: list[str]) -> None:
        y_col = (settings.y_cols or [""])[0]
        x = self.df[settings.x_col]
        x_numeric = pd.to_numeric(x, errors="coerce")
        x = x_numeric if x_numeric.notna().sum() >= len(x_numeric) * 0.5 else x.astype(str)
        y = self._numeric_series(y_col)
        yerr = self._numeric_series(settings.error_col) if settings.error_col else None
        ax.errorbar(
            x,
            y,
            yerr=yerr,
            label=y_col,
            color=colors[0],
            linewidth=settings.line_width,
            marker=settings.marker or "o",
            markersize=settings.marker_size,
            capsize=4 if yerr is not None else 0,
        )

    def _plot_histogram(self, ax: Any, settings: PlotSettings, colors: list[str]) -> None:
        for index, y_col in enumerate(settings.y_cols or []):
            values = self._numeric_series(y_col).dropna()
            ax.hist(values, bins=settings.bins, alpha=0.65, label=y_col, color=colors[index % len(colors)])

    def _plot_density(self, ax: Any, settings: PlotSettings, colors: list[str]) -> None:
        for index, y_col in enumerate(settings.y_cols or []):
            values = self._numeric_series(y_col).dropna()
            if values.empty:
                continue
            counts, edges = np.histogram(values, bins=settings.bins, density=True)
            centers = (edges[:-1] + edges[1:]) / 2
            if len(counts) >= 5:
                kernel = np.ones(5) / 5
                counts = np.convolve(counts, kernel, mode="same")
            color = colors[index % len(colors)]
            ax.plot(centers, counts, label=y_col, color=color, linewidth=settings.line_width)
            ax.fill_between(centers, counts, color=color, alpha=0.18)

    def _plot_ecdf(self, ax: Any, settings: PlotSettings, colors: list[str]) -> None:
        for index, y_col in enumerate(settings.y_cols or []):
            values = np.sort(self._numeric_series(y_col).dropna().to_numpy())
            if values.size == 0:
                continue
            y = np.arange(1, values.size + 1) / values.size
            ax.step(values, y, where="post", label=y_col, color=colors[index % len(colors)], linewidth=settings.line_width)

    def _plot_boxplot(self, ax: Any, settings: PlotSettings, colors: list[str]) -> None:
        y_cols = settings.y_cols or []
        data = [self._numeric_series(col).dropna() for col in y_cols]
        box = ax.boxplot(data, labels=y_cols, patch_artist=True)
        for patch, color in zip(box["boxes"], colors * max(1, len(y_cols))):
            patch.set_facecolor(color)
            patch.set_alpha(0.6)

    def _plot_violin(self, ax: Any, settings: PlotSettings, colors: list[str]) -> None:
        y_cols = settings.y_cols or []
        data = [self._numeric_series(col).dropna() for col in y_cols]
        violin = ax.violinplot(data, showmeans=True, showextrema=True)
        for index, body in enumerate(violin["bodies"]):
            body.set_facecolor(colors[index % len(colors)])
            body.set_edgecolor("#374151")
            body.set_alpha(0.55)
        ax.set_xticks(range(1, len(y_cols) + 1))
        ax.set_xticklabels(y_cols, rotation=20, ha="right")

    def _plot_stem(self, ax: Any, settings: PlotSettings, colors: list[str]) -> None:
        x = self._numeric_series(settings.x_col)
        for index, y_col in enumerate(settings.y_cols or []):
            markerline, stemlines, baseline = ax.stem(x, self._numeric_series(y_col), label=y_col)
            color = colors[index % len(colors)]
            markerline.set_color(color)
            stemlines.set_color(color)
            baseline.set_color("#9ca3af")

    def _plot_lollipop(self, ax: Any, settings: PlotSettings, colors: list[str]) -> None:
        x = self.df[settings.x_col].astype(str)
        indices = np.arange(len(x))
        for index, y_col in enumerate(settings.y_cols or []):
            y = self._numeric_series(y_col)
            color = colors[index % len(colors)]
            ax.vlines(indices, 0, y, color=color, alpha=0.7, linewidth=settings.line_width)
            ax.scatter(indices, y, color=color, s=max(30, settings.marker_size**2), label=y_col, zorder=3)
        ax.set_xticks(indices)
        ax.set_xticklabels(x, rotation=30, ha="right")

    def _plot_heatmap(self, ax: Any, settings: PlotSettings) -> None:
        numeric_cols = settings.y_cols or self.numeric_columns()
        if len(numeric_cols) < 2:
            raise ValueError("相關熱圖至少需要兩個數值欄位。")
        corr = self.df[numeric_cols].apply(pd.to_numeric, errors="coerce").corr()
        image = ax.imshow(corr.values, cmap="coolwarm", vmin=-1, vmax=1)
        ax.set_xticks(range(len(corr.columns)))
        ax.set_yticks(range(len(corr.columns)))
        ax.set_xticklabels(corr.columns, rotation=45, ha="right")
        ax.set_yticklabels(corr.columns)
        for i in range(len(corr.columns)):
            for j in range(len(corr.columns)):
                ax.text(j, i, f"{corr.values[i, j]:.2f}", ha="center", va="center", fontsize=max(7, settings.font_size - 2))
        self.figure_colorbar = image

    def _plot_hist2d(self, ax: Any, settings: PlotSettings) -> None:
        y_col = (settings.y_cols or [""])[0]
        frame = self._numeric_frame([settings.x_col, y_col])
        image = ax.hist2d(frame[settings.x_col], frame[y_col], bins=settings.bins, cmap="viridis")
        self._add_colorbar(ax, image[3], "Count")

    def _plot_hexbin(self, ax: Any, settings: PlotSettings) -> None:
        y_col = (settings.y_cols or [""])[0]
        frame = self._numeric_frame([settings.x_col, y_col])
        artist = ax.hexbin(frame[settings.x_col], frame[y_col], gridsize=settings.bins, cmap="viridis", mincnt=1)
        self._add_colorbar(ax, artist, "Count")

    def _plot_contour(self, ax: Any, settings: PlotSettings, filled: bool) -> None:
        y_col = (settings.y_cols or [""])[0]
        frame, triangulation = self._triangulation_frame(settings.x_col, y_col, settings.z_col)
        if filled:
            artist = ax.tricontourf(triangulation, frame[settings.z_col], levels=min(settings.bins, 40), cmap="viridis")
        else:
            artist = ax.tricontour(triangulation, frame[settings.z_col], levels=min(settings.bins, 40), cmap="viridis", linewidths=1.0)
            ax.clabel(artist, inline=True, fontsize=max(7, settings.font_size - 2))
        self._add_colorbar(ax, artist, settings.z_col)

    def _plot_radar(self, ax: Any, settings: PlotSettings, colors: list[str]) -> None:
        y_cols = settings.y_cols or []
        if len(y_cols) < 3:
            raise ValueError("雷達圖至少需要三個 Y 欄位。")
        values = [self._numeric_series(col).mean(skipna=True) for col in y_cols]
        angles = np.linspace(0, 2 * np.pi, len(y_cols), endpoint=False).tolist()
        values += values[:1]
        angles += angles[:1]
        ax.plot(angles, values, color=colors[0], linewidth=settings.line_width, marker=settings.marker or "o")
        ax.fill(angles, values, color=colors[0], alpha=0.18)
        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(y_cols)

    def _plot_polar(self, ax: Any, settings: PlotSettings, colors: list[str], mode: str) -> None:
        theta = self._numeric_series(settings.x_col)
        for index, y_col in enumerate(settings.y_cols or []):
            radius = self._numeric_series(y_col)
            color = colors[index % len(colors)]
            if mode == "line":
                ax.plot(theta, radius, label=y_col, color=color, linewidth=settings.line_width, marker=settings.marker or None)
            else:
                ax.scatter(theta, radius, label=y_col, color=color, s=max(20, settings.marker_size**2))

    def _plot_pie(self, ax: Any, settings: PlotSettings, colors: list[str], donut: bool) -> None:
        y_col = (settings.y_cols or [self.numeric_columns()[0]])[0]
        values = self._numeric_series(y_col).dropna()
        if settings.x_col:
            labels = self.df.loc[values.index, settings.x_col].astype(str)
        else:
            labels = [str(i + 1) for i in range(len(values))]
        ax.pie(values, labels=labels, autopct="%1.1f%%", colors=colors * max(1, len(values)), startangle=90)
        if donut:
            ax.add_artist(Circle((0, 0), 0.58, fc="white"))
        ax.axis("equal")

    def _plot_3d(self, ax: Any, settings: PlotSettings, colors: list[str], chart_key: str) -> None:
        y_col = (settings.y_cols or [""])[0]
        frame = self._numeric_frame([settings.x_col, y_col, settings.z_col])
        if frame.empty:
            raise ValueError("3D 圖表需要有效的 X、Y 和 Z 數值。")
        x = frame[settings.x_col]
        y = frame[y_col]
        z = frame[settings.z_col]
        ax.view_init(elev=settings.elev, azim=settings.azim)
        if chart_key == "scatter3d":
            c = self._color_values(settings)
            c = c.reindex(frame.index) if isinstance(c, pd.Series) else z
            artist = ax.scatter(x, y, z, c=c, cmap="viridis", s=max(25, settings.marker_size**2), depthshade=True)
            self._add_colorbar(ax, artist, settings.color_col or settings.z_col)
        elif chart_key == "line3d":
            ax.plot(x, y, z, color=colors[0], linewidth=settings.line_width, marker=settings.marker or None, label=y_col)
        elif chart_key in {"surface3d", "wireframe3d", "contour3d"}:
            frame, triangulation = self._triangulation_frame(settings.x_col, y_col, settings.z_col)
            z = frame[settings.z_col]
            if chart_key == "surface3d":
                artist = ax.plot_trisurf(triangulation, z, cmap="viridis", alpha=0.88, linewidth=0.25)
                self._add_colorbar(ax, artist, settings.z_col)
            elif chart_key == "wireframe3d":
                ax.plot_trisurf(triangulation, z, color=colors[0], alpha=0.18, edgecolor=colors[0], linewidth=0.7)
            else:
                ax.tricontour(triangulation, z, levels=min(settings.bins, 35), cmap="viridis")
        elif chart_key == "bar3d":
            dx = dy = np.full(len(frame), 0.45)
            z_base = np.zeros(len(frame))
            ax.bar3d(x, y, z_base, dx, dy, z, color=colors[0], alpha=0.72, shade=True)

    def _decorate_axes(self, ax: Any, fig: Figure, settings: PlotSettings, chart_key: str) -> None:
        ax.set_title(settings.title, fontsize=settings.font_size + 2, pad=settings.title_pad, wrap=True)
        if chart_key in {"scatter3d", "line3d", "surface3d", "wireframe3d", "bar3d", "contour3d"}:
            ax.set_xlabel(settings.xlabel or settings.x_col)
            ax.set_ylabel(settings.ylabel or ", ".join(settings.y_cols or []))
            ax.set_zlabel(settings.zlabel or settings.z_col)
            ax.xaxis.labelpad = settings.axis_label_pad
            ax.yaxis.labelpad = settings.axis_label_pad
            ax.zaxis.labelpad = settings.axis_label_pad
        elif chart_key not in {"heatmap", "radar", "polar_line", "polar_scatter", "pie", "donut"}:
            ax.set_xlabel(settings.xlabel or settings.x_col)
            ax.set_ylabel(settings.ylabel or ", ".join(settings.y_cols or []))
            ax.xaxis.labelpad = settings.axis_label_pad
            ax.yaxis.labelpad = settings.axis_label_pad
        if hasattr(ax, "tick_params"):
            ax.tick_params(axis="both", pad=settings.tick_label_pad)
        if settings.grid and chart_key not in {"heatmap", "pie", "donut"}:
            ax.grid(True, color="#d1d5db", linewidth=0.7, alpha=0.75)
        bottom_legend = False
        if settings.legend and settings.legend_position != "無" and chart_key not in {"heatmap", "pie", "donut"}:
            handles, labels = ax.get_legend_handles_labels()
            if handles and labels:
                legend_position = settings.legend_position
                if legend_position == "自動":
                    bottom_legend = chart_key not in {"radar", "polar_line", "polar_scatter"} and len(labels) >= 3
                elif legend_position == "底部":
                    bottom_legend = True
                if bottom_legend:
                    ax.legend(
                        frameon=False,
                        loc="upper center",
                        bbox_to_anchor=(0.5, -0.16),
                        borderaxespad=0,
                        ncol=min(2, len(labels)),
                        fontsize=max(8, settings.font_size - 1),
                    )
                elif legend_position == "右側":
                    ax.legend(
                        frameon=False,
                        loc="center left",
                        bbox_to_anchor=(1.02, 0.5),
                        borderaxespad=0,
                        fontsize=max(8, settings.font_size - 1),
                    )
                elif legend_position == "左上":
                    ax.legend(frameon=False, loc="upper left", fontsize=max(8, settings.font_size - 1))
                else:
                    ax.legend(frameon=False, loc="upper right", fontsize=max(8, settings.font_size - 1))
        if chart_key == "heatmap" and getattr(self, "figure_colorbar", None) is not None:
            fig.colorbar(self.figure_colorbar, ax=ax, fraction=0.046, pad=0.04, label="Pearson r")
        if hasattr(ax, "spines"):
            for spine in ax.spines.values():
                spine.set_color("#374151")
                spine.set_linewidth(0.8)
        if chart_key not in {"heatmap", "radar", "polar_line", "polar_scatter", "pie", "donut"}:
            visible_xticks = [tick for tick in ax.get_xticklabels() if tick.get_text()]
            rotation = settings.x_tick_rotation if settings.x_tick_rotation else (30 if len(visible_xticks) > 8 else 0)
            if rotation:
                for tick in visible_xticks:
                    tick.set_rotation(rotation)
                    tick.set_ha("right")
        if settings.tight_layout:
            try:
                with warnings.catch_warnings():
                    warnings.filterwarnings("error", message="Tight layout not applied.*")
                    fig.tight_layout(pad=1.6)
            except Warning:
                if chart_key in {"scatter3d", "line3d", "surface3d", "wireframe3d", "bar3d", "contour3d"}:
                    fig.subplots_adjust(left=0.04, right=0.92, top=0.86, bottom=0.08)
                elif chart_key in {"radar", "polar_line", "polar_scatter"}:
                    fig.subplots_adjust(left=0.12, right=0.88, top=0.86, bottom=0.12)
                else:
                    fig.subplots_adjust(left=0.14, right=0.94, top=0.86, bottom=0.16)
        if bottom_legend:
            fig.subplots_adjust(bottom=0.28)
        manual_adjust: dict[str, float] = {}
        if settings.margin_left > 0:
            manual_adjust["left"] = settings.margin_left
        if settings.margin_right > 0:
            manual_adjust["right"] = 1 - settings.margin_right
        if settings.margin_top > 0:
            manual_adjust["top"] = 1 - settings.margin_top
        if settings.margin_bottom > 0:
            manual_adjust["bottom"] = settings.margin_bottom
        if manual_adjust:
            fig.subplots_adjust(**manual_adjust)

    def _show_figure(self, fig: Figure) -> None:
        for child in self.plot_container.winfo_children():
            child.destroy()
        self.figure = fig
        self.canvas_widget = FigureCanvasTkAgg(fig, master=self.plot_container)
        canvas = self.canvas_widget.get_tk_widget()
        canvas.pack(fill="both", expand=True)
        self.toolbar = NavigationToolbar2Tk(self.canvas_widget, self.plot_container, pack_toolbar=False)
        self.toolbar.update()
        self.toolbar.pack(fill="x")
        self.canvas_widget.draw()

    def apply_selected_template(self) -> None:
        name = self.template_var.get()
        template = BUILTIN_TEMPLATES.get(name)
        if template is None:
            path = TEMPLATE_DIR / f"{name}.json"
            if path.exists():
                template = self._read_template_file(path)
        if not template:
            messagebox.showwarning("模板不存在", "沒有找到所選模板。")
            return
        self.apply_template(template, update_chart_type=True)
        self.set_status(f"已套用模板：{name}")

    def apply_template(self, template: dict[str, Any], update_chart_type: bool = False) -> None:
        if update_chart_type and template.get("chart_type"):
            self.chart_type_var.set(self._normalize_chart_type(template["chart_type"]))
        self.width_var.set(self._template_number(template, "width", self.width_var, float))
        self.height_var.set(self._template_number(template, "height", self.height_var, float))
        self.dpi_var.set(self._template_number(template, "dpi", self.dpi_var, int))
        self.font_size_var.set(self._template_number(template, "font_size", self.font_size_var, int))
        self.line_width_var.set(self._template_number(template, "line_width", self.line_width_var, float))
        self.marker_size_var.set(self._template_number(template, "marker_size", self.marker_size_var, float))
        self.marker_var.set(str(template.get("marker", self.marker_var.get()) or "None"))
        palette = str(template.get("palette", self.palette_var.get()))
        self.palette_var.set(palette if palette in PALETTES else self.palette_var.get())
        self.grid_var.set(self._template_bool(template, "grid", self.grid_var))
        self.legend_var.set(self._template_bool(template, "legend", self.legend_var))
        self.tight_layout_var.set(self._template_bool(template, "tight_layout", self.tight_layout_var))
        if hasattr(self, "title_pad_var"):
            self.title_pad_var.set(self._template_number(template, "title_pad", self.title_pad_var, int))
        if hasattr(self, "axis_label_pad_var"):
            self.axis_label_pad_var.set(self._template_number(template, "axis_label_pad", self.axis_label_pad_var, int))
        if hasattr(self, "tick_label_pad_var"):
            self.tick_label_pad_var.set(self._template_number(template, "tick_label_pad", self.tick_label_pad_var, int))
        if hasattr(self, "x_tick_rotation_var"):
            self.x_tick_rotation_var.set(self._template_number(template, "x_tick_rotation", self.x_tick_rotation_var, int))
        if hasattr(self, "legend_position_var"):
            legend_position = str(template.get("legend_position", self.legend_position_var.get()))
            self.legend_position_var.set(legend_position if legend_position in {"自動", "右上", "右側", "底部", "左上", "無"} else "自動")
        if hasattr(self, "margin_left_var"):
            self.margin_left_var.set(self._template_number(template, "margin_left", self.margin_left_var, float))
        if hasattr(self, "margin_right_var"):
            self.margin_right_var.set(self._template_number(template, "margin_right", self.margin_right_var, float))
        if hasattr(self, "margin_top_var"):
            self.margin_top_var.set(self._template_number(template, "margin_top", self.margin_top_var, float))
        if hasattr(self, "margin_bottom_var"):
            self.margin_bottom_var.set(self._template_number(template, "margin_bottom", self.margin_bottom_var, float))
        if hasattr(self, "bins_var"):
            self.bins_var.set(self._template_number(template, "bins", self.bins_var, int))
        if hasattr(self, "elev_var"):
            self.elev_var.set(self._template_number(template, "elev", self.elev_var, int))
        if hasattr(self, "azim_var"):
            self.azim_var.set(self._template_number(template, "azim", self.azim_var, int))

    def save_current_template(self) -> None:
        name = simpledialog.askstring("保存模板", "模板名稱：", parent=self)
        if not name:
            return
        safe_name = "".join(ch for ch in name.strip() if ch not in "\\/:*?\"<>|").strip()
        if not safe_name:
            messagebox.showwarning("名稱無效", "模板名稱不可為空或僅包含非法字符。")
            return
        path = TEMPLATE_DIR / f"{safe_name}.json"
        template = asdict(self.collect_settings())
        for key in ("x_col", "y_cols", "z_col", "error_col", "group_col", "size_col", "color_col", "title", "xlabel", "ylabel", "zlabel"):
            template.pop(key, None)
        path.write_text(json.dumps(template, ensure_ascii=False, indent=2), encoding="utf-8")
        self.template_combo.configure(values=self._template_names())
        self.template_var.set(safe_name)
        self.set_status(f"已保存模板：{path}")

    def import_template(self) -> None:
        path = filedialog.askopenfilename(
            title="導入模板 JSON",
            initialdir=str(APP_HOME),
            filetypes=[("JSON", "*.json"), ("所有文件", "*.*")],
        )
        if not path:
            return
        try:
            data = self._read_template_file(Path(path))
            name = Path(path).stem
            dest = TEMPLATE_DIR / f"{name}.json"
            dest.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            self.template_combo.configure(values=self._template_names())
            self.template_var.set(name)
            self.set_status(f"已導入模板：{name}")
        except Exception as exc:
            messagebox.showerror("導入失敗", f"模板 JSON 無法讀取：\n{exc}")

    def export_template(self) -> None:
        path = filedialog.asksaveasfilename(
            title="導出模板",
            initialdir=str(EXPORT_DIR),
            initialfile="sciplot_template.json",
            defaultextension=".json",
            filetypes=[("JSON", "*.json")],
        )
        if not path:
            return
        template = asdict(self.collect_settings())
        for key in ("x_col", "y_cols", "z_col", "error_col", "group_col", "size_col", "color_col", "title", "xlabel", "ylabel", "zlabel"):
            template.pop(key, None)
        Path(path).write_text(json.dumps(template, ensure_ascii=False, indent=2), encoding="utf-8")
        self.set_status(f"已導出模板：{path}")

    def open_export_dialog(self) -> None:
        if self.figure is None:
            messagebox.showwarning("沒有圖表", "請先生成圖表。")
            return

        dialog = tk.Toplevel(self)
        dialog.title("導出圖表")
        dialog.geometry("520x330")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()
        dialog.configure(bg=self.colors["app"])
        dialog.columnconfigure(1, weight=1)
        dialog.rowconfigure(0, weight=1)

        fmt_var = tk.StringVar(value="png")
        name_var = tk.StringVar(value=self._default_export_name())
        folder_var = tk.StringVar(value=str(EXPORT_DIR))
        dpi_var = tk.IntVar(value=self._int_var(self.dpi_var, 300, 72, 1200))
        transparent_var = tk.BooleanVar(value=False)

        left = ttk.Frame(dialog, style="Surface.TFrame", padding=14)
        left.grid(row=0, column=0, sticky="nsew", padx=(12, 8), pady=12)
        ttk.Label(left, text="文件格式", style="Title.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 10))
        for row, (label, value) in enumerate((("PNG", "png"), ("SVG", "svg"), ("PDF", "pdf")), start=1):
            ttk.Radiobutton(left, text=label, variable=fmt_var, value=value).grid(row=row, column=0, sticky="w", pady=8)

        right = ttk.Frame(dialog, style="Surface.TFrame", padding=16)
        right.grid(row=0, column=1, sticky="nsew", padx=(0, 12), pady=12)
        right.columnconfigure(1, weight=1)
        ttk.Label(right, text="導出設置", style="Title.TLabel").grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 12))
        ttk.Label(right, text="文件名", style="Surface.TLabel").grid(row=1, column=0, sticky="w", pady=6)
        ttk.Entry(right, textvariable=name_var).grid(row=1, column=1, columnspan=2, sticky="ew", pady=6)
        ttk.Label(right, text="保存位置", style="Surface.TLabel").grid(row=2, column=0, sticky="w", pady=6)
        ttk.Entry(right, textvariable=folder_var).grid(row=2, column=1, sticky="ew", pady=6)
        ttk.Button(right, text="瀏覽", command=lambda: self._choose_export_folder(folder_var)).grid(row=2, column=2, padx=(8, 0), pady=6)
        ttk.Label(right, text="分辨率", style="Surface.TLabel").grid(row=3, column=0, sticky="w", pady=6)
        ttk.Spinbox(right, textvariable=dpi_var, from_=72, to=1200, increment=10, width=10).grid(row=3, column=1, sticky="w", pady=6)
        ttk.Label(right, text="dpi", style="Surface.TLabel").grid(row=3, column=2, sticky="w", pady=6)
        ttk.Checkbutton(right, text="透明背景", variable=transparent_var).grid(row=4, column=1, sticky="w", pady=8)

        button_bar = ttk.Frame(right, style="Surface.TFrame")
        button_bar.grid(row=5, column=0, columnspan=3, sticky="e", pady=(28, 0))
        ttk.Button(button_bar, text="取消", command=dialog.destroy).grid(row=0, column=0, padx=6)
        ttk.Button(
            button_bar,
            text="導出",
            style="Accent.TButton",
            command=lambda: self._export_from_dialog(dialog, fmt_var, name_var, folder_var, dpi_var, transparent_var),
        ).grid(row=0, column=1, padx=6)

    def _choose_export_folder(self, folder_var: tk.StringVar) -> None:
        path = filedialog.askdirectory(title="選擇導出位置", initialdir=folder_var.get() or str(EXPORT_DIR))
        if path:
            folder_var.set(path)

    def _default_export_name(self) -> str:
        raw = self.title_var.get().strip() if hasattr(self, "title_var") else ""
        if not raw:
            raw = "sciplot_figure"
        return self._safe_file_stem(raw)

    def _safe_file_stem(self, value: str) -> str:
        name = Path(value).name.strip()
        safe = "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "_" for ch in name).strip("._ ")
        reserved = {"con", "prn", "aux", "nul", "com1", "com2", "com3", "com4", "lpt1", "lpt2", "lpt3"}
        if not safe or safe.lower() in reserved:
            return "sciplot_figure"
        return safe[:120]

    def _export_from_dialog(
        self,
        dialog: tk.Toplevel,
        fmt_var: tk.StringVar,
        name_var: tk.StringVar,
        folder_var: tk.StringVar,
        dpi_var: tk.IntVar,
        transparent_var: tk.BooleanVar,
    ) -> None:
        fmt = fmt_var.get().lower()
        folder = Path(folder_var.get()).expanduser()
        name = self._safe_file_stem(name_var.get().strip() or "sciplot_figure")
        if not name.lower().endswith(f".{fmt}"):
            name = f"{name}.{fmt}"
        try:
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / name
            self._save_current_figure(path, max(72, int(dpi_var.get())), bool(transparent_var.get()))
            self.set_status(f"已導出圖表：{path}")
            self.refresh_home_lists()
            dialog.destroy()
        except Exception as exc:
            messagebox.showerror("導出失敗", f"保存圖表時出錯：\n{exc}")

    def export_figure(self, fmt: str) -> None:
        if self.figure is None:
            messagebox.showwarning("沒有圖表", "請先生成圖表。")
            return
        path = filedialog.asksaveasfilename(
            title=f"導出 {fmt.upper()}",
            initialdir=str(EXPORT_DIR),
            initialfile=f"sciplot_figure.{fmt}",
            defaultextension=f".{fmt}",
            filetypes=[(fmt.upper(), f"*.{fmt}")],
        )
        if not path:
            return
        try:
            self._save_current_figure(Path(path), self._int_var(self.dpi_var, 300, 72, 1200), False)
            self.set_status(f"已導出圖表：{path}")
            self.refresh_home_lists()
        except Exception as exc:
            messagebox.showerror("導出失敗", f"保存圖表時出錯：\n{exc}")

    def _save_current_figure(self, path: Path, dpi: int, transparent: bool) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        settings = self.current_settings
        chart_key = CHART_TYPES.get(settings.chart_type, "line")
        export_figure = self._create_plot_figure(settings, chart_key, dpi)
        save_kwargs: dict[str, Any] = {"dpi": dpi, "transparent": transparent}
        if transparent:
            save_kwargs["facecolor"] = "none"
        else:
            save_kwargs["facecolor"] = export_figure.get_facecolor()
        export_figure.savefig(path, **save_kwargs)

    def save_project(self) -> None:
        if self.df.empty:
            messagebox.showwarning("沒有數據", "請先載入數據再保存項目。")
            return
        path = filedialog.asksaveasfilename(
            title="保存 SciPlot 項目",
            initialdir=str(USER_DATA_DIR),
            initialfile="project.sciplot.json",
            defaultextension=".json",
            filetypes=[("SciPlot 項目", "*.json")],
        )
        if not path:
            return
        payload = {
            "app": APP_NAME,
            "version": APP_VERSION,
            "data_source": self.data_source,
            "columns": list(self.df.columns),
            "records": self.df.replace({np.nan: None}).to_dict(orient="records"),
            "settings": asdict(self.collect_settings()),
        }
        try:
            Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            self.set_status(f"已保存項目：{path}")
            self.refresh_home_lists()
        except Exception as exc:
            messagebox.showerror("保存失敗", f"保存項目時出錯：\n{exc}")

    def load_project(self) -> None:
        path = filedialog.askopenfilename(
            title="載入 SciPlot 項目",
            initialdir=str(USER_DATA_DIR),
            filetypes=[("SciPlot 項目", "*.json"), ("所有文件", "*.*")],
        )
        if not path:
            return
        try:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
            self.df = pd.DataFrame(payload.get("records", []), columns=payload.get("columns") or None)
            self.data_source = payload.get("data_source", path)
            self.source_var.set(self.data_source)
            self.refresh_after_data_load()
            settings = payload.get("settings", {})
            self.restore_settings(settings)
            self.render_plot(silent=True)
            self.navigate("plot")
            self.set_status(f"已載入項目：{path}")
        except Exception as exc:
            messagebox.showerror("載入失敗", f"項目文件無法讀取：\n{exc}")

    def restore_settings(self, settings: dict[str, Any]) -> None:
        self.chart_type_var.set(self._normalize_chart_type(settings.get("chart_type", self.chart_type_var.get())))
        self.x_col_var.set(settings.get("x_col", self.x_col_var.get()))
        self.z_col_var.set(settings.get("z_col", ""))
        self.error_col_var.set(settings.get("error_col", ""))
        self.group_col_var.set(settings.get("group_col", ""))
        self.size_col_var.set(settings.get("size_col", ""))
        self.color_col_var.set(settings.get("color_col", ""))
        self.title_var.set(settings.get("title", ""))
        self.xlabel_var.set(settings.get("xlabel", ""))
        self.ylabel_var.set(settings.get("ylabel", ""))
        self.zlabel_var.set(settings.get("zlabel", ""))
        self.apply_template(settings, update_chart_type=False)
        y_cols = settings.get("y_cols") or []
        self._select_y_columns([col for col in y_cols if col in self.numeric_columns()])

    def check_for_updates(self) -> None:
        if self._update_check_running:
            self.set_status("正在檢查更新，請稍候。")
            return
        self._update_check_running = True
        self.set_status("正在檢查 GitHub 最新版本...")
        thread = threading.Thread(target=self._check_for_updates_worker, daemon=True)
        thread.start()

    def _check_for_updates_worker(self) -> None:
        try:
            request = urllib.request.Request(
                GITHUB_LATEST_RELEASE_API,
                headers={"Accept": "application/vnd.github+json", "User-Agent": f"SciPlot/{APP_VERSION}"},
            )
            with urllib.request.urlopen(request, timeout=15) as response:
                payload = json.loads(response.read().decode("utf-8"))
            self.after(0, lambda: self._handle_update_result(payload, None))
        except Exception as exc:
            self.after(0, lambda: self._handle_update_result(None, exc))

    def _handle_update_result(self, release: dict[str, Any] | None, error: Exception | None) -> None:
        self._update_check_running = False
        if error is not None or not release:
            self.set_status("更新檢查失敗。")
            messagebox.showerror("檢查更新失敗", f"無法連接 GitHub Releases：\n{error}")
            return
        latest_version = str(release.get("tag_name") or release.get("name") or "").lstrip("v")
        if not latest_version:
            self.set_status("未找到可用更新。")
            messagebox.showinfo("檢查更新", "未找到可用的正式版本。")
            return
        if not self._is_newer_version(latest_version, APP_VERSION):
            self.set_status(f"已是最新版本：{APP_VERSION}")
            messagebox.showinfo("檢查更新", f"目前已是最新版本：{APP_VERSION}")
            return

        asset = self._preferred_update_asset(release.get("assets") or [])
        if asset is None:
            self.set_status(f"發現新版本 {latest_version}。")
            if messagebox.askyesno("發現新版本", f"SciPlot {latest_version} 已發布。\n\n未找到適合此平台的安裝包。是否打開 Release 頁面？"):
                webbrowser.open(str(release.get("html_url") or GITHUB_RELEASES_URL))
            return

        asset_name = str(asset.get("name", ""))
        if messagebox.askyesno(
            "發現新版本",
            f"SciPlot {latest_version} 已發布。\n\n是否下載並開啟安裝包？\n{asset_name}",
        ):
            self._start_update_download(asset, latest_version)
        else:
            self.set_status(f"發現新版本 {latest_version}，尚未下載。")

    def _version_key(self, value: str) -> tuple[int, int, int]:
        parts = [int(part) for part in re.findall(r"\d+", value)]
        parts = (parts + [0, 0, 0])[:3]
        return parts[0], parts[1], parts[2]

    def _is_newer_version(self, latest: str, current: str) -> bool:
        return self._version_key(latest) > self._version_key(current)

    def _preferred_update_asset(self, assets: list[dict[str, Any]]) -> dict[str, Any] | None:
        names = [(asset, str(asset.get("name", "")).lower()) for asset in assets]
        if sys.platform.startswith("win"):
            for asset, name in names:
                if name.endswith(".msi") and "windows" in name:
                    return asset
            for asset, name in names:
                if name.endswith(".msi"):
                    return asset
        if sys.platform == "darwin":
            machine = platform.machine().lower()
            preferred = "arm64" if machine in {"arm64", "aarch64"} else "intel"
            for asset, name in names:
                if name.endswith(".dmg") and preferred in name:
                    return asset
            for asset, name in names:
                if name.endswith(".dmg"):
                    return asset
        return None

    def _start_update_download(self, asset: dict[str, Any], latest_version: str) -> None:
        url = str(asset.get("browser_download_url") or "")
        asset_name = self._safe_file_stem(str(asset.get("name") or f"SciPlot-{latest_version}"))
        if not url:
            messagebox.showerror("下載失敗", "此版本沒有可下載的安裝包連結。")
            return
        updates_dir = USER_DATA_DIR / "updates"
        updates_dir.mkdir(parents=True, exist_ok=True)
        destination = updates_dir / asset_name
        self.set_status(f"正在下載 SciPlot {latest_version}...")
        thread = threading.Thread(target=self._download_update_worker, args=(url, destination), daemon=True)
        thread.start()

    def _download_update_worker(self, url: str, destination: Path) -> None:
        try:
            request = urllib.request.Request(url, headers={"User-Agent": f"SciPlot/{APP_VERSION}"})
            with urllib.request.urlopen(request, timeout=60) as response, destination.open("wb") as file:
                while True:
                    chunk = response.read(1024 * 512)
                    if not chunk:
                        break
                    file.write(chunk)
            self.after(0, lambda: self._handle_update_downloaded(destination, None))
        except Exception as exc:
            self.after(0, lambda: self._handle_update_downloaded(destination, exc))

    def _handle_update_downloaded(self, path: Path, error: Exception | None) -> None:
        if error is not None:
            self.set_status("更新下載失敗。")
            messagebox.showerror("下載失敗", f"無法下載安裝包：\n{error}")
            return
        self.set_status(f"更新安裝包已下載：{path.name}")
        if messagebox.askyesno("下載完成", f"安裝包已下載：\n{path}\n\n是否現在開啟？安裝時請先關閉 SciPlot。"):
            self._open_update_installer(path)

    def _open_update_installer(self, path: Path) -> None:
        try:
            if sys.platform.startswith("win"):
                os.startfile(path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                webbrowser.open(path.as_uri())
        except Exception as exc:
            messagebox.showerror("開啟失敗", f"無法開啟安裝包：\n{exc}")

    def show_about(self) -> None:
        messagebox.showinfo(
            "關於 SciPlot",
            (
                f"{APP_NAME} {APP_VERSION}\n\n"
                "本地科研繪圖工具，適合學生、課堂與實驗報告使用。\n"
                "不包含模板市場、付費購買、賬號系統或商業追蹤。"
            ),
        )

    def set_status(self, message: str) -> None:
        self.status_var.set(message)


def main() -> None:
    if "--smoke-test" in sys.argv:
        run_smoke_test()
        return
    if "--gui-smoke" in sys.argv:
        run_gui_smoke_test()
        return
    app = SciPlotApp()
    app.mainloop()


def run_smoke_test() -> None:
    sample_path = APP_HOME / "sample_data" / "example_measurements.csv"
    if not sample_path.exists():
        sample_path = SAMPLE_DIR / "example_measurements.csv"
    if not sample_path.exists():
        raise FileNotFoundError("sample_data/example_measurements.csv not found")

    df = pd.read_csv(sample_path)
    fig = Figure(figsize=(6.4, 3.8), dpi=150)
    ax = fig.add_subplot(111)
    for group_name, group_df in df.groupby("group"):
        ax.plot(group_df["time_s"], group_df["signal_a"], marker="o", linewidth=1.8, label=f"{group_name} signal_a")
        ax.plot(group_df["time_s"], group_df["signal_b"], marker="s", linewidth=1.8, label=f"{group_name} signal_b")
    ax.set_title("SciPlot smoke test")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Signal intensity")
    ax.grid(True, color="#d1d5db", linewidth=0.7)
    ax.legend(frameon=False)
    fig.tight_layout()
    for suffix in ("png", "svg", "pdf"):
        output_path = EXPORT_DIR / f"smoke_test.{suffix}"
        fig.savefig(output_path, dpi=150)
        if not output_path.exists() or output_path.stat().st_size < 1000:
            raise RuntimeError(f"{suffix.upper()} smoke export failed")
        print(output_path)


def run_gui_smoke_test() -> None:
    app = SciPlotApp(visible=False)
    app.update_idletasks()
    app.update()
    app.load_sample_data(silent=True)
    app.render_plot(silent=True, persist=False)
    if app.df.empty or app.figure is None:
        app.destroy()
        raise RuntimeError("GUI smoke test failed: sample figure was not rendered")
    app.destroy()
    print("gui-ok")


if __name__ == "__main__":
    main()
