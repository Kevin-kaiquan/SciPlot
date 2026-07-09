from __future__ import annotations

import sys
import threading
import traceback
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk
from PIL import Image, ImageTk


APP_TITLE = "SciPlot 正在啟動"


def _app_dir() -> Path:
    return Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[1]


def _resource_path(*parts: str) -> Path:
    resource_root = Path(getattr(sys, "_MEIPASS", _app_dir()))
    candidate = resource_root.joinpath(*parts)
    if candidate.exists():
        return candidate
    return _app_dir().joinpath(*parts)


def _apply_splash_icon(window: tk.Tk) -> None:
    try:
        ico = _resource_path("logo", "SciPlot.ico")
        png = _resource_path("logo", "SciPlot.png")
        if ico.exists() and sys.platform.startswith("win"):
            window.iconbitmap(str(ico))
        if png.exists():
            window._icon_image = tk.PhotoImage(file=str(png))
            window.iconphoto(True, window._icon_image)
    except tk.TclError:
        pass


def _load_splash_logo(max_size: int) -> ImageTk.PhotoImage | None:
    try:
        png = _resource_path("logo", "SciPlot.png")
        if not png.exists():
            return None
        image = Image.open(png).convert("RGBA")
        image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
        return ImageTk.PhotoImage(image)
    except Exception:
        return None


def run_with_splash() -> None:
    splash = tk.Tk()
    splash.title(APP_TITLE)
    _apply_splash_icon(splash)
    splash.geometry("460x250")
    splash.resizable(False, False)
    splash.configure(bg="#f8fafc")

    splash.update_idletasks()
    width = splash.winfo_width()
    height = splash.winfo_height()
    x = (splash.winfo_screenwidth() // 2) - (width // 2)
    y = (splash.winfo_screenheight() // 2) - (height // 2)
    splash.geometry(f"{width}x{height}+{x}+{y}")

    frame = tk.Frame(splash, bg="#f8fafc", padx=26, pady=22)
    frame.pack(fill="both", expand=True)
    logo_image = _load_splash_logo(82)
    if logo_image is not None:
        splash._logo_image = logo_image
        tk.Label(frame, image=logo_image, bg="#f8fafc", borderwidth=0).pack(anchor="center", pady=(0, 8))
    tk.Label(frame, text="SciPlot", bg="#f8fafc", fg="#0f172a", font=("Microsoft YaHei UI", 18, "bold")).pack(anchor="center")
    tk.Label(
        frame,
        text="正在載入科研繪圖引擎，首次啟動可能需要十幾秒。",
        bg="#f8fafc",
        fg="#475569",
        font=("Microsoft YaHei UI", 10),
    ).pack(anchor="center", pady=(12, 12))
    progress = ttk.Progressbar(frame, mode="indeterminate")
    progress.pack(fill="x")
    progress.start(12)

    result: dict[str, object] = {}

    def load_app() -> None:
        try:
            from sciplot_app import SciPlotApp

            result["app_class"] = SciPlotApp
        except BaseException:
            result["error"] = traceback.format_exc()

    def poll_loader() -> None:
        if "app_class" in result:
            progress.stop()
            app_class = result["app_class"]
            splash.destroy()
            app = app_class()
            app.mainloop()
            return
        if "error" in result:
            progress.stop()
            log_path = _write_startup_log(str(result["error"]))
            messagebox.showerror("SciPlot 啟動失敗", f"啟動時發生錯誤。\n\n錯誤日誌：{log_path}")
            splash.destroy()
            return
        splash.after(100, poll_loader)

    threading.Thread(target=load_app, daemon=True).start()
    splash.after(100, poll_loader)
    splash.mainloop()


def _write_startup_log(content: str) -> Path:
    app_dir = _app_dir()
    runtime = app_dir / "runtime"
    runtime.mkdir(parents=True, exist_ok=True)
    log_path = runtime / "startup_error.log"
    log_path.write_text(content, encoding="utf-8")
    return log_path


def main() -> None:
    if "--smoke-test" in sys.argv or "--gui-smoke" in sys.argv:
        from sciplot_app import main as app_main

        app_main()
        return
    run_with_splash()


if __name__ == "__main__":
    main()
