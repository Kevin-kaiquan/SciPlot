from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any


def get_app_home() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


APP_HOME = get_app_home()
RUNTIME_DIR = APP_HOME / "runtime"
RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(RUNTIME_DIR / "matplotlib"))

import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

import numpy as np
import pandas as pd
from matplotlib import rcParams
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure


APP_NAME = "SciPlot"
APP_VERSION = "1.0.0"

RESOURCE_ROOT = Path(getattr(sys, "_MEIPASS", APP_HOME))
TEMPLATE_DIR = APP_HOME / "templates"
SAMPLE_DIR = RESOURCE_ROOT / "sample_data"
USER_DATA_DIR = APP_HOME / "user_data"
EXPORT_DIR = APP_HOME / "exports"

for directory in (TEMPLATE_DIR, USER_DATA_DIR, EXPORT_DIR, RUNTIME_DIR / "matplotlib"):
    directory.mkdir(parents=True, exist_ok=True)


def seed_packaged_files() -> None:
    resource_templates = RESOURCE_ROOT / "templates"
    if resource_templates.exists():
        for source in resource_templates.glob("*.json"):
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
    "散點圖": "scatter",
    "柱狀圖": "bar",
    "誤差棒": "errorbar",
    "直方圖": "histogram",
    "箱線圖": "boxplot",
    "相關熱圖": "heatmap",
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
    error_col: str = ""
    group_col: str = ""
    title: str = ""
    xlabel: str = ""
    ylabel: str = ""
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


class ScrollFrame(ttk.Frame):
    def __init__(self, parent: tk.Widget) -> None:
        super().__init__(parent)
        self.canvas = tk.Canvas(self, highlightthickness=0, borderwidth=0)
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
        self.figure: Figure | None = None
        self.canvas_widget: FigureCanvasTkAgg | None = None
        self.toolbar: NavigationToolbar2Tk | None = None
        self.current_settings = PlotSettings()

        self._vars: dict[str, tk.Variable] = {}
        self._build_style()
        self._build_ui()
        self._load_initial_sample()

    def _set_initial_geometry(self) -> None:
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        width = min(1080, max(920, screen_w - 240))
        height = min(720, max(620, screen_h - 180))
        self.minsize(min(980, width), min(640, height))
        x = 40 if screen_w > width + 80 else max(0, (screen_w - width) // 2)
        y = 40 if screen_h > height + 80 else max(0, (screen_h - height) // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")

    def _build_style(self) -> None:
        self.colors = {
            "app": "#f5f7fb",
            "surface": "#ffffff",
            "surface_2": "#f8fafc",
            "border": "#dbe3ef",
            "text": "#111827",
            "muted": "#6b7280",
            "primary": "#2563eb",
            "primary_dark": "#1d4ed8",
            "sidebar": "#0f2347",
            "sidebar_2": "#15315f",
            "sidebar_active": "#2f6df6",
        }
        self.configure(bg=self.colors["app"])
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure(".", font=("Microsoft YaHei UI", 9), background=self.colors["app"])
        style.configure("TFrame", background=self.colors["app"])
        style.configure("App.TFrame", background=self.colors["app"])
        style.configure("Surface.TFrame", background=self.colors["surface"])
        style.configure("Card.TFrame", background=self.colors["surface"])
        style.configure("TLabel", background=self.colors["app"], foreground=self.colors["text"])
        style.configure("Surface.TLabel", background=self.colors["surface"], foreground=self.colors["text"])
        style.configure("Muted.TLabel", background=self.colors["surface"], foreground=self.colors["muted"])
        style.configure("Hero.TLabel", background=self.colors["app"], foreground=self.colors["text"], font=("Microsoft YaHei UI", 18, "bold"))
        style.configure("Subhero.TLabel", background=self.colors["app"], foreground=self.colors["muted"], font=("Microsoft YaHei UI", 10))
        style.configure("CardTitle.TLabel", background=self.colors["surface"], foreground=self.colors["text"], font=("Microsoft YaHei UI", 10, "bold"))
        style.configure("TButton", padding=(10, 5), background=self.colors["surface"])
        style.configure("Tool.TButton", padding=(8, 4), background=self.colors["surface"])
        style.configure("Accent.TButton", padding=(10, 6), foreground="#ffffff", background=self.colors["primary"])
        style.map("Accent.TButton", background=[("active", "#1d4ed8")])
        style.configure("Title.TLabel", background=self.colors["surface"], foreground=self.colors["text"], font=("Microsoft YaHei UI", 12, "bold"))
        style.configure("Status.TLabel", background=self.colors["app"], foreground="#4b5563")
        style.configure("TNotebook", background=self.colors["surface"], borderwidth=0)
        style.configure("TNotebook.Tab", padding=(14, 7), background="#eef2f7")
        style.map("TNotebook.Tab", background=[("selected", "#ffffff")], foreground=[("selected", self.colors["primary"])])
        style.configure("Treeview", rowheight=25, bordercolor=self.colors["border"], lightcolor=self.colors["border"], darkcolor=self.colors["border"])
        style.configure("Treeview.Heading", font=("Microsoft YaHei UI", 9, "bold"))

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
        sidebar = tk.Frame(self, bg=self.colors["sidebar"], width=108)
        sidebar.grid(row=0, column=0, sticky="ns")
        sidebar.grid_propagate(False)
        sidebar.columnconfigure(0, weight=1)

        brand = tk.Label(
            sidebar,
            text="SciPlot",
            bg=self.colors["sidebar"],
            fg="#ffffff",
            font=("Microsoft YaHei UI", 11, "bold"),
            pady=18,
        )
        brand.grid(row=0, column=0, sticky="ew")

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
        tk.Label(sidebar, text="就緒", bg=self.colors["sidebar"], fg="#b9c7df", font=("Microsoft YaHei UI", 8)).grid(
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
            pady=10,
            font=("Microsoft YaHei UI", 9, "bold" if key == "home" else "normal"),
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
                font=("Microsoft YaHei UI", 9, "bold" if active else "normal"),
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
            ("導入數據", "CSV、TSV、TXT、Excel", self.open_data),
            ("新建圖表", "從示例或當前數據開始", lambda: self.navigate("plot")),
            ("打開項目", "載入已保存的項目文件", self.load_project),
            ("導入模板", "使用同學共享的 JSON 模板", self.import_template),
        ]
        for index, (title, desc, command) in enumerate(actions):
            row = index // 2
            col = index % 2
            card = self._home_action_card(parent, title, desc, command)
            card.grid(row=row, column=col, sticky="nsew", padx=(0 if col == 0 else 8, 0 if col == 1 else 8), pady=(0, 14))

        recent_projects = self._home_list_panel(parent, "最近項目")
        recent_projects.grid(row=2, column=0, sticky="nsew", padx=(0, 8))
        self.recent_projects_frame = recent_projects.body

        recent_files = self._home_list_panel(parent, "最近文件")
        recent_files.grid(row=2, column=1, sticky="nsew", padx=(8, 0))
        self.recent_files_frame = recent_files.body

    def _home_action_card(self, parent: ttk.Frame, title: str, description: str, command: Any) -> tk.Frame:
        card = tk.Frame(parent, bg=self.colors["surface"], highlightthickness=1, highlightbackground=self.colors["border"])
        card.configure(width=230, height=148)
        card.grid_propagate(False)
        card.columnconfigure(0, weight=1)
        tk.Label(card, text=title, bg=self.colors["surface"], fg=self.colors["text"], font=("Microsoft YaHei UI", 11, "bold")).grid(
            row=0, column=0, sticky="w", padx=18, pady=(18, 4)
        )
        tk.Label(
            card,
            text=description,
            bg=self.colors["surface"],
            fg=self.colors["muted"],
            font=("Microsoft YaHei UI", 9),
            wraplength=185,
            justify="left",
        ).grid(
            row=1, column=0, sticky="w", padx=18
        )
        ttk.Button(card, text="開始", style="Tool.TButton", command=command).grid(row=2, column=0, sticky="ew", padx=18, pady=(16, 18))
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

        left = ttk.Frame(paned, width=310, style="Surface.TFrame")
        center = ttk.Frame(paned, style="Surface.TFrame")
        right = ttk.Frame(paned, width=300, style="Surface.TFrame")
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
        help_menu.add_command(label="關於", command=self.show_about)
        menu.add_cascade(label="幫助", menu=help_menu)
        self.configure(menu=menu)

    def _build_controls(self, parent: ttk.Frame) -> None:
        notebook = ttk.Notebook(parent)
        notebook.grid(row=0, column=0, sticky="nsew")
        self.controls_notebook = notebook

        data_tab = ScrollFrame(notebook)
        plot_tab = ScrollFrame(notebook)

        notebook.add(data_tab, text="數據")
        notebook.add(plot_tab, text="繪圖")

        self._build_data_tab(data_tab.inner)
        self._build_plot_tab(plot_tab.inner)

    def _build_side_settings(self, parent: ttk.Frame) -> None:
        notebook = ttk.Notebook(parent)
        notebook.grid(row=0, column=0, sticky="nsew")
        self.side_settings_notebook = notebook

        style_tab = ScrollFrame(notebook)
        template_tab = ScrollFrame(notebook)
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

    def _load_initial_sample(self) -> None:
        self.load_sample_data(silent=True)
        if not self.df.empty:
            self.apply_template(BUILTIN_TEMPLATES["SciPlot Classic"], update_chart_type=True)
            numeric_cols = self.numeric_columns()
            if "time_s" in self.df.columns:
                self.x_col_var.set("time_s")
            if "group" in self.df.columns:
                self.group_col_var.set("group")
            if numeric_cols:
                self._select_y_columns([col for col in ["signal_a", "signal_b"] if col in numeric_cols] or numeric_cols[:1])
            self.title_var.set("示例實驗信號")
            self.xlabel_var.set("Time (s)")
            self.ylabel_var.set("Signal intensity")
            self.render_plot(silent=True)

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
                self.render_plot(silent=True)
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
            self.render_plot(silent=True)
            self.set_status(f"已載入數據：{Path(path).name}")
        except Exception as exc:
            messagebox.showerror("載入失敗", f"無法讀取數據文件：\n{exc}")

    def _read_data_file(self, path: Path) -> pd.DataFrame:
        suffix = path.suffix.lower()
        if suffix in {".xlsx", ".xls"}:
            df = pd.read_excel(path)
        elif suffix == ".tsv":
            df = pd.read_csv(path, sep="\t")
        else:
            df = pd.read_csv(path, sep=None, engine="python")
        if df.empty or len(df.columns) == 0:
            raise ValueError("文件沒有可用數據。")
        return df

    def refresh_after_data_load(self) -> None:
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
        self.group_combo.configure(values=columns)
        if not self.x_col_var.get() and self.df.columns.size:
            self.x_col_var.set(str(self.df.columns[0]))

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
            series = pd.to_numeric(self.df[col], errors="coerce")
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
            error_col=self.error_col_var.get(),
            group_col=self.group_col_var.get(),
            title=self.title_var.get(),
            xlabel=self.xlabel_var.get(),
            ylabel=self.ylabel_var.get(),
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

    def render_plot(self, silent: bool = False) -> None:
        if self.df.empty:
            if not silent:
                messagebox.showwarning("沒有數據", "請先載入 CSV 或 Excel 數據。")
            return
        settings = self.collect_settings()
        chart_key = CHART_TYPES.get(settings.chart_type, "line")
        if chart_key not in {"histogram", "boxplot", "heatmap"} and not settings.x_col:
            messagebox.showwarning("缺少 X 軸", "請選擇 X 軸欄位。")
            return
        if chart_key != "heatmap" and not settings.y_cols:
            messagebox.showwarning("缺少 Y 軸", "請至少選擇一個 Y 軸欄位。")
            return

        try:
            self.current_settings = settings
            preview_dpi = min(settings.dpi, 150)
            fig = Figure(figsize=(settings.width, settings.height), dpi=preview_dpi)
            ax = fig.add_subplot(111)
            fig.patch.set_facecolor("#ffffff")
            ax.set_facecolor("#ffffff")

            colors = PALETTES.get(settings.palette, PALETTES["期刊藍灰"])
            rcParams["font.size"] = settings.font_size
            self._plot_by_type(ax, chart_key, settings, colors)
            self._decorate_axes(ax, fig, settings, chart_key)
            self._show_figure(fig)
            self.set_status(f"圖表已更新：{settings.chart_type}")
        except Exception as exc:
            messagebox.showerror("繪圖失敗", f"生成圖表時出錯：\n{exc}")

    def _plot_by_type(self, ax: Any, chart_key: str, settings: PlotSettings, colors: list[str]) -> None:
        if chart_key == "line":
            self._plot_xy(ax, settings, colors, mode="line")
        elif chart_key == "scatter":
            self._plot_xy(ax, settings, colors, mode="scatter")
        elif chart_key == "bar":
            self._plot_bar(ax, settings, colors)
        elif chart_key == "errorbar":
            self._plot_errorbar(ax, settings, colors)
        elif chart_key == "histogram":
            self._plot_histogram(ax, settings, colors)
        elif chart_key == "boxplot":
            self._plot_boxplot(ax, settings, colors)
        elif chart_key == "heatmap":
            self._plot_heatmap(ax, settings)
        else:
            self._plot_xy(ax, settings, colors, mode="line")

    def _numeric_series(self, col: str) -> pd.Series:
        return pd.to_numeric(self.df[col], errors="coerce")

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
            else:
                ax.scatter(x, y, label=y_col, color=color, s=settings.marker_size**2)

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
            ax.hist(values, bins="auto", alpha=0.65, label=y_col, color=colors[index % len(colors)])

    def _plot_boxplot(self, ax: Any, settings: PlotSettings, colors: list[str]) -> None:
        y_cols = settings.y_cols or []
        data = [self._numeric_series(col).dropna() for col in y_cols]
        box = ax.boxplot(data, labels=y_cols, patch_artist=True)
        for patch, color in zip(box["boxes"], colors * max(1, len(y_cols))):
            patch.set_facecolor(color)
            patch.set_alpha(0.6)

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

    def _decorate_axes(self, ax: Any, fig: Figure, settings: PlotSettings, chart_key: str) -> None:
        ax.set_title(settings.title, fontsize=settings.font_size + 2, pad=12)
        if chart_key != "heatmap":
            ax.set_xlabel(settings.xlabel or settings.x_col)
            ax.set_ylabel(settings.ylabel or ", ".join(settings.y_cols or []))
        if settings.grid and chart_key != "heatmap":
            ax.grid(True, color="#d1d5db", linewidth=0.7, alpha=0.75)
        if settings.legend and chart_key not in {"heatmap"}:
            handles, labels = ax.get_legend_handles_labels()
            if handles and labels:
                ax.legend(frameon=False)
        if chart_key == "heatmap" and hasattr(self, "figure_colorbar"):
            fig.colorbar(self.figure_colorbar, ax=ax, fraction=0.046, pad=0.04, label="Pearson r")
        for spine in ax.spines.values():
            spine.set_color("#374151")
            spine.set_linewidth(0.8)
        if settings.tight_layout:
            fig.tight_layout()

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
                template = json.loads(path.read_text(encoding="utf-8"))
        if not template:
            messagebox.showwarning("模板不存在", "沒有找到所選模板。")
            return
        self.apply_template(template, update_chart_type=True)
        self.set_status(f"已套用模板：{name}")

    def apply_template(self, template: dict[str, Any], update_chart_type: bool = False) -> None:
        if update_chart_type and template.get("chart_type"):
            self.chart_type_var.set(template["chart_type"])
        self.width_var.set(float(template.get("width", self.width_var.get())))
        self.height_var.set(float(template.get("height", self.height_var.get())))
        self.dpi_var.set(int(template.get("dpi", self.dpi_var.get())))
        self.font_size_var.set(int(template.get("font_size", self.font_size_var.get())))
        self.line_width_var.set(float(template.get("line_width", self.line_width_var.get())))
        self.marker_size_var.set(float(template.get("marker_size", self.marker_size_var.get())))
        self.marker_var.set(str(template.get("marker", self.marker_var.get()) or "None"))
        self.palette_var.set(str(template.get("palette", self.palette_var.get())))
        self.grid_var.set(bool(template.get("grid", self.grid_var.get())))
        self.legend_var.set(bool(template.get("legend", self.legend_var.get())))
        self.tight_layout_var.set(bool(template.get("tight_layout", self.tight_layout_var.get())))

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
        template.pop("x_col", None)
        template.pop("y_cols", None)
        template.pop("error_col", None)
        template.pop("group_col", None)
        template.pop("title", None)
        template.pop("xlabel", None)
        template.pop("ylabel", None)
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
            data = json.loads(Path(path).read_text(encoding="utf-8"))
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
        for key in ("x_col", "y_cols", "error_col", "group_col", "title", "xlabel", "ylabel"):
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
        safe = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in raw).strip("_")
        return safe or "sciplot_figure"

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
        name = name_var.get().strip() or "sciplot_figure"
        if not name.lower().endswith(f".{fmt}"):
            name = f"{name}.{fmt}"
        try:
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / name
            self.figure.savefig(path, dpi=max(72, int(dpi_var.get())), bbox_inches="tight", transparent=bool(transparent_var.get()))
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
            self.figure.savefig(path, dpi=self._int_var(self.dpi_var, 300, 72, 1200), bbox_inches="tight")
            self.set_status(f"已導出圖表：{path}")
            self.refresh_home_lists()
        except Exception as exc:
            messagebox.showerror("導出失敗", f"保存圖表時出錯：\n{exc}")

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
        self.chart_type_var.set(settings.get("chart_type", self.chart_type_var.get()))
        self.x_col_var.set(settings.get("x_col", self.x_col_var.get()))
        self.error_col_var.set(settings.get("error_col", ""))
        self.group_col_var.set(settings.get("group_col", ""))
        self.title_var.set(settings.get("title", ""))
        self.xlabel_var.set(settings.get("xlabel", ""))
        self.ylabel_var.set(settings.get("ylabel", ""))
        self.apply_template(settings, update_chart_type=False)
        y_cols = settings.get("y_cols") or []
        self._select_y_columns([col for col in y_cols if col in self.numeric_columns()])

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
    output_path = EXPORT_DIR / "smoke_test.png"
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
    fig.savefig(output_path, dpi=150)
    print(output_path)


def run_gui_smoke_test() -> None:
    app = SciPlotApp(visible=False)
    app.update_idletasks()
    app.update()
    if app.df.empty:
        app.destroy()
        raise RuntimeError("GUI smoke test failed: sample data was not loaded")
    if app.figure is None:
        app.destroy()
        raise RuntimeError("GUI smoke test failed: initial figure was not rendered")
    app.destroy()
    print("gui-ok")


if __name__ == "__main__":
    main()
