from __future__ import annotations

import hashlib
import io
import json
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from .data_io import normalize_dataframe, read_data_file
from .models import PlotSettings
from .version import APP_NAME, APP_VERSION


PROJECT_FORMAT_VERSION = 2
MAX_EMBEDDED_SESSION_ROWS = 5000


@dataclass
class ProjectData:
    dataframe: pd.DataFrame
    settings: PlotSettings
    source_name: str = ""


@dataclass
class SessionData(ProjectData):
    source_path: str = ""


class SessionSourceChangedError(RuntimeError):
    pass


def _source_name(value: str) -> str:
    return value.replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]


def dataframe_to_json(frame: pd.DataFrame) -> str:
    return frame.to_json(orient="table", date_format="iso", date_unit="ms", index=False)


def dataframe_from_json(value: str) -> pd.DataFrame:
    return normalize_dataframe(pd.read_json(io.StringIO(value), orient="table"))


def save_project(path: Path, dataframe: pd.DataFrame, settings: PlotSettings, source_name: str = "") -> Path:
    if path.suffix.lower() != ".sciplot":
        path = path.with_suffix(".sciplot")
    path.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "format": "SciPlot Project",
        "format_version": PROJECT_FORMAT_VERSION,
        "app_version": APP_VERSION,
        "source_name": _source_name(source_name) if source_name else "",
        "row_count": len(dataframe),
        "columns": [str(column) for column in dataframe.columns],
        "settings": settings.to_dict(),
    }
    temporary = path.with_suffix(path.suffix + ".tmp")
    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        archive.writestr("data.json", dataframe_to_json(dataframe))
    temporary.replace(path)
    return path


def load_project(path: Path) -> ProjectData:
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path, "r") as archive:
            names = set(archive.namelist())
            if {"manifest.json", "data.json"} - names:
                raise ValueError("The SciPlot project is incomplete.")
            manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
            data = archive.read("data.json").decode("utf-8")
        return ProjectData(
            dataframe=dataframe_from_json(data),
            settings=PlotSettings.from_dict(manifest.get("settings")),
            source_name=str(manifest.get("source_name") or path.name),
        )

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("The project root must be a JSON object.")
    records = payload.get("records")
    if not isinstance(records, list):
        raise ValueError("The legacy project does not contain records.")
    frame = normalize_dataframe(pd.DataFrame(records, columns=payload.get("columns") or None))
    return ProjectData(
        dataframe=frame,
        settings=PlotSettings.from_dict(payload.get("settings")),
        source_name=_source_name(str(payload.get("data_source") or path.name)),
    )


def _source_fingerprint(path: Path) -> dict[str, Any]:
    stat = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as source:
        first = source.read(1024 * 1024)
        digest.update(first)
        if stat.st_size > len(first):
            source.seek(max(0, stat.st_size - 1024 * 1024))
            digest.update(source.read(1024 * 1024))
    return {"size": stat.st_size, "mtime_ns": stat.st_mtime_ns, "edge_sha256": digest.hexdigest()}


def save_session(path: Path, dataframe: pd.DataFrame, settings: PlotSettings, source_path: str) -> None:
    source = Path(source_path) if source_path else None
    source_exists = bool(source and source.exists() and source.is_file())
    payload: dict[str, Any] = {
        "app": APP_NAME,
        "app_version": APP_VERSION,
        "format_version": PROJECT_FORMAT_VERSION,
        "settings": settings.to_dict(),
        "source_path": str(source) if source_exists else "",
        "source_name": source.name if source_exists and source else "",
        "row_count": len(dataframe),
    }
    if len(dataframe) <= MAX_EMBEDDED_SESSION_ROWS or not source_exists:
        payload["data"] = dataframe_to_json(dataframe)
    elif source is not None:
        payload["source_fingerprint"] = _source_fingerprint(source)

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


def load_session(path: Path) -> SessionData | None:
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    settings = PlotSettings.from_dict(payload.get("settings"))
    if payload.get("data"):
        return SessionData(
            dataframe=dataframe_from_json(str(payload["data"])),
            settings=settings,
            source_name=str(payload.get("source_name") or ""),
            source_path=str(payload.get("source_path") or ""),
        )

    source_path = Path(str(payload.get("source_path") or ""))
    if not source_path.exists():
        return None
    expected = payload.get("source_fingerprint") or {}
    if expected and _source_fingerprint(source_path) != expected:
        raise SessionSourceChangedError(str(source_path))
    return SessionData(
        dataframe=read_data_file(source_path),
        settings=settings,
        source_name=source_path.name,
        source_path=str(source_path),
    )
