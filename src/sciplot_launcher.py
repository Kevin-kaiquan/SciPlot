from __future__ import annotations

import sys
import threading
import traceback
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk


APP_TITLE = "SciPlot 正在啟動"


def run_with_splash() -> None:
    splash = tk.Tk()
    splash.title(APP_TITLE)
    splash.geometry("420x180")
    splash.resizable(False, False)
    splash.configure(bg="#f8fafc")

    splash.update_idletasks()
    width = splash.winfo_width()
    height = splash.winfo_height()
    x = (splash.winfo_screenwidth() // 2) - (width // 2)
    y = (splash.winfo_screenheight() // 2) - (height // 2)
    splash.geometry(f"{width}x{height}+{x}+{y}")

    frame = ttk.Frame(splash, padding=24)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="SciPlot", font=("Microsoft YaHei UI", 15, "bold")).pack(anchor="w")
    ttk.Label(frame, text="正在載入科研繪圖引擎，首次啟動可能需要十幾秒。").pack(anchor="w", pady=(12, 10))
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
    app_dir = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[1]
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
