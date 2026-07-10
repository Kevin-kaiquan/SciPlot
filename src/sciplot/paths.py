from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

from .version import APP_NAME


def source_root() -> Path:
    return Path(__file__).resolve().parents[2]


def executable_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return source_root()


def resource_root() -> Path:
    return Path(getattr(sys, "_MEIPASS", source_root()))


def _can_write(directory: Path) -> bool:
    try:
        directory.mkdir(parents=True, exist_ok=True)
        probe = directory / ".sciplot_write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True
    except OSError:
        return False


def user_data_root() -> Path:
    override = os.environ.get("SCIPLOT_APP_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()

    if not getattr(sys, "frozen", False):
        return source_root()

    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME

    app_dir = executable_dir()
    installed = (app_dir / "sciplot_installed.flag").exists()
    if sys.platform.startswith("win") and not installed and _can_write(app_dir):
        return app_dir

    if sys.platform.startswith("win"):
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if base:
            return Path(base) / APP_NAME
    return Path.home() / f".{APP_NAME.lower()}"


ROOT = source_root()
APP_DIR = executable_dir()
RESOURCE_ROOT = resource_root()
APP_DATA_ROOT = user_data_root()
RUNTIME_DIR = APP_DATA_ROOT / "runtime"
TEMPLATE_DIR = APP_DATA_ROOT / "templates"
PROJECT_DIR = APP_DATA_ROOT / "projects"
EXPORT_DIR = APP_DATA_ROOT / "exports"
UPDATE_DIR = APP_DATA_ROOT / "updates"
SESSION_PATH = APP_DATA_ROOT / "last_session.json"
UPDATE_STATE_PATH = APP_DATA_ROOT / "update_state.json"
SAMPLE_DIR = RESOURCE_ROOT / "sample_data"
PACKAGED_TEMPLATE_DIR = RESOURCE_ROOT / "templates"
LOGO_DIR = RESOURCE_ROOT / "logo"
APP_ICON_PNG = LOGO_DIR / "SciPlot.png"
APP_ICON_ICO = LOGO_DIR / "SciPlot.ico"
APP_ICON_ICNS = LOGO_DIR / "SciPlot.icns"


def initialize_paths() -> None:
    for directory in (RUNTIME_DIR, TEMPLATE_DIR, PROJECT_DIR, EXPORT_DIR, UPDATE_DIR):
        directory.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(RUNTIME_DIR / "matplotlib"))
    (RUNTIME_DIR / "matplotlib").mkdir(parents=True, exist_ok=True)

    if PACKAGED_TEMPLATE_DIR.exists() and PACKAGED_TEMPLATE_DIR.resolve() != TEMPLATE_DIR.resolve():
        for source in PACKAGED_TEMPLATE_DIR.glob("*.json"):
            destination = TEMPLATE_DIR / source.name
            if not destination.exists():
                shutil.copy2(source, destination)


def startup_log_path() -> Path:
    initialize_paths()
    return RUNTIME_DIR / "startup_error.log"


initialize_paths()
