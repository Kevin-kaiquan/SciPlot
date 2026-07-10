from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import pandas as pd


TEXT_ENCODINGS = ("utf-8-sig", "utf-8", "gb18030", "cp1252")


def make_unique_columns(columns: list[Any]) -> list[str]:
    seen: dict[str, int] = {}
    unique: list[str] = []
    for raw in columns:
        name = str(raw).strip() or "Column"
        count = seen.get(name, 0)
        seen[name] = count + 1
        unique.append(name if count == 0 else f"{name}_{count + 1}")
    return unique


def normalize_dataframe(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty or len(frame.columns) == 0:
        raise ValueError("The file does not contain usable tabular data.")
    result = frame.copy()
    result.columns = make_unique_columns(list(result.columns))
    return result


def read_data_file(path: Path, sheet_name: str | int = 0) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix in {".xlsx", ".xls"}:
        return normalize_dataframe(pd.read_excel(path, sheet_name=sheet_name))
    if suffix == ".tsv":
        return normalize_dataframe(_read_text(path, sep="\t", sniff=False))
    if suffix == ".csv":
        return normalize_dataframe(_read_text(path, sep=",", sniff=True))
    if suffix in {".txt", ".dat"}:
        return normalize_dataframe(_read_text(path, sep=None, sniff=True))
    raise ValueError(f"Unsupported data format: {suffix or path.name}")


def _read_text(path: Path, sep: str | None, sniff: bool) -> pd.DataFrame:
    last_error: Exception | None = None
    for encoding in TEXT_ENCODINGS:
        try:
            if sep is None:
                return pd.read_csv(path, sep=None, engine="python", encoding=encoding)
            frame = pd.read_csv(path, sep=sep, encoding=encoding)
            if sniff and len(frame.columns) <= 1:
                detected = pd.read_csv(path, sep=None, engine="python", encoding=encoding)
                if len(detected.columns) > len(frame.columns):
                    return detected
            return frame
        except (UnicodeDecodeError, pd.errors.ParserError) as exc:
            last_error = exc
            if sniff:
                try:
                    return pd.read_csv(path, sep=None, engine="python", encoding=encoding)
                except Exception as sniff_error:
                    last_error = sniff_error
    if last_error:
        raise last_error
    raise ValueError("The file could not be read.")


def numeric_columns(frame: pd.DataFrame, minimum_ratio: float = 0.6) -> list[str]:
    result: list[str] = []
    for column in frame.columns:
        source = frame[column]
        non_empty = int(source.notna().sum())
        if non_empty == 0:
            continue
        numeric_count = int(pd.to_numeric(source, errors="coerce").notna().sum())
        required = max(1, math.ceil(non_empty * minimum_ratio))
        if numeric_count >= required:
            result.append(str(column))
    return result


def suggest_columns(frame: pd.DataFrame) -> dict[str, Any]:
    columns = [str(column) for column in frame.columns]
    numeric = numeric_columns(frame)
    x_column = columns[0] if columns else ""
    lower_to_name = {column.lower(): column for column in columns}
    for candidate in ("time", "time_s", "date", "datetime", "x", "index"):
        if candidate in lower_to_name:
            x_column = lower_to_name[candidate]
            break

    y_candidates = [column for column in numeric if column != x_column]
    group_column = ""
    for candidate in ("group", "condition", "category", "series", "treatment", "class"):
        if candidate in lower_to_name:
            group_column = lower_to_name[candidate]
            break

    z_column = y_candidates[1] if len(y_candidates) > 1 else ""
    error_column = ""
    for column in numeric:
        lowered = column.lower()
        if "error" in lowered or lowered.endswith("_sd") or lowered.endswith("_se"):
            error_column = column
            break
    return {
        "x": x_column,
        "y": y_candidates[:1] or numeric[:1],
        "z": z_column,
        "error": error_column,
        "group": group_column,
        "numeric": numeric,
    }
