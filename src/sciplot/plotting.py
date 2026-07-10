from __future__ import annotations

import sys
import warnings
from pathlib import Path
from typing import Any

import matplotlib.tri as mtri
import numpy as np
import pandas as pd
from matplotlib import rc_context
from matplotlib.figure import Figure
from matplotlib.patches import Circle

from .models import CHART_DEFINITIONS, PALETTES, PlotSettings


THREE_D_CHARTS = {"scatter3d", "line3d", "surface3d", "wireframe3d", "bar3d", "contour3d"}
POLAR_CHARTS = {"radar", "polar_line", "polar_scatter"}
NO_X_REQUIRED = {"histogram", "density", "ecdf", "boxplot", "violin", "heatmap", "radar", "pie", "donut"}
Y_OPTIONAL = {"heatmap"}
Z_REQUIRED = THREE_D_CHARTS | {"contour", "contourf"}
SINGLE_Y_CHARTS = {"bubble", "errorbar", "hist2d", "hexbin", "contour", "contourf", "pie", "donut"} | THREE_D_CHARTS
BIN_CHARTS = {"histogram", "density", "hist2d", "hexbin", "contour", "contourf", "surface3d", "wireframe3d", "contour3d"}


def chart_requirements(chart_type: str) -> dict[str, bool]:
    return {
        "x": chart_type not in NO_X_REQUIRED or chart_type in {"pie", "donut"},
        "y": chart_type not in Y_OPTIONAL,
        "single_y": chart_type in SINGLE_Y_CHARTS,
        "z": chart_type in Z_REQUIRED,
        "error": chart_type == "errorbar",
        "size": chart_type == "bubble",
        "color": chart_type in {"bubble", "scatter3d"},
        "group": chart_type in {"line", "step", "scatter", "area", "bar", "barh", "errorbar"},
        "bins": chart_type in BIN_CHARTS,
        "3d": chart_type in THREE_D_CHARTS,
        "polar": chart_type in {"polar_line", "polar_scatter"},
        "radar": chart_type == "radar",
    }


def validate_settings(dataframe: pd.DataFrame, settings: PlotSettings) -> None:
    if dataframe.empty:
        raise ValueError("Load data before generating a figure.")
    if settings.chart_type not in CHART_DEFINITIONS:
        raise ValueError("Unknown chart type.")
    if settings.chart_type not in NO_X_REQUIRED and not settings.x_col:
        raise ValueError("Select an X column for this chart.")
    if settings.chart_type not in Y_OPTIONAL and not settings.y_cols:
        raise ValueError("Select at least one Y column for this chart.")
    if settings.chart_type in Z_REQUIRED and not settings.z_col:
        raise ValueError("Select a Z / intensity column for this chart.")
    if settings.chart_type == "errorbar" and not settings.error_col:
        raise ValueError("Select an error column for the error-bar chart.")
    selected = [settings.x_col, *(settings.y_cols or []), settings.z_col, settings.error_col, settings.group_col, settings.size_col, settings.color_col]
    missing = [column for column in selected if column and column not in dataframe.columns]
    if missing:
        raise ValueError(f"Columns are missing from the data: {', '.join(dict.fromkeys(missing))}")


def _font_candidates() -> list[str]:
    if sys.platform.startswith("win"):
        return ["Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI", "SimHei", "DejaVu Sans"]
    if sys.platform == "darwin":
        return ["PingFang TC", "PingFang SC", "Heiti TC", "Arial Unicode MS", "DejaVu Sans"]
    return ["Noto Sans CJK TC", "Noto Sans CJK SC", "Noto Sans", "DejaVu Sans"]


class PlotEngine:
    def __init__(self, dataframe: pd.DataFrame) -> None:
        self.set_data(dataframe)

    def set_data(self, dataframe: pd.DataFrame) -> None:
        self.dataframe = dataframe
        self._numeric_cache: dict[str, pd.Series] = {}
        self._colorbar_artist: Any = None

    def create_figure(self, settings: PlotSettings, dpi: int | None = None) -> Figure:
        validate_settings(self.dataframe, settings)
        chart_type = settings.chart_type
        render_dpi = int(dpi or min(settings.dpi, 160))
        rc = {
            "font.family": "sans-serif",
            "font.sans-serif": _font_candidates(),
            "font.size": settings.font_size,
            "axes.unicode_minus": False,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "svg.fonttype": "path",
        }
        with rc_context(rc):
            figure = Figure(figsize=(settings.width, settings.height), dpi=render_dpi)
            if chart_type in THREE_D_CHARTS:
                axes = figure.add_subplot(111, projection="3d")
            elif chart_type in POLAR_CHARTS:
                axes = figure.add_subplot(111, projection="polar")
            else:
                axes = figure.add_subplot(111)
            figure.patch.set_facecolor("#ffffff")
            axes.set_facecolor("#ffffff")
            self._colorbar_artist = None
            self._plot(axes, chart_type, settings)
            artists = self._decorate(axes, figure, settings)
            figure._sciplot_axes = axes  # type: ignore[attr-defined]
            figure._sciplot_artists = artists  # type: ignore[attr-defined]
            return figure

    def _numeric(self, column: str) -> pd.Series:
        if column not in self._numeric_cache:
            self._numeric_cache[column] = pd.to_numeric(self.dataframe[column], errors="coerce")
        return self._numeric_cache[column]

    def _numeric_frame(self, columns: list[str], settings: PlotSettings) -> pd.DataFrame:
        unique = list(dict.fromkeys(column for column in columns if column))
        frame = self.dataframe[unique].copy()
        for column in unique:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
        if settings.missing_policy == "zero":
            return frame.fillna(0)
        if settings.missing_policy == "interpolate":
            return frame.interpolate(limit_direction="both").dropna()
        return frame.dropna()

    def _xy_frame(self, x_column: str, y_column: str, settings: PlotSettings, frame: pd.DataFrame | None = None) -> tuple[pd.Series, pd.Series]:
        source = self.dataframe if frame is None else frame
        x_raw = source[x_column]
        y = pd.to_numeric(source[y_column], errors="coerce")
        x_numeric = pd.to_numeric(x_raw, errors="coerce")
        numeric_x = x_numeric.notna().sum() >= max(1, int(x_raw.notna().sum() * 0.6))
        working = pd.DataFrame({"_x": x_numeric if numeric_x else x_raw, "_y": y}, index=source.index)
        working = working.dropna(subset=["_x"])
        if settings.sort_x and numeric_x and len(working) > 1:
            working = working.sort_values("_x")
        if settings.missing_policy == "zero":
            working["_y"] = working["_y"].fillna(0)
        elif settings.missing_policy == "interpolate":
            working["_y"] = working["_y"].interpolate(limit_direction="both")
        working = working.dropna(subset=["_y"])
        if not numeric_x:
            working["_x"] = working["_x"].astype(str)
        return working["_x"], working["_y"]

    def _triangulation(self, x_column: str, y_column: str, z_column: str, settings: PlotSettings) -> tuple[pd.DataFrame, mtri.Triangulation]:
        frame = self._numeric_frame([x_column, y_column, z_column], settings)
        frame = frame.groupby([x_column, y_column], as_index=False)[z_column].mean()
        if len(frame) < 3:
            raise ValueError("Contour and surface charts need at least three different X/Y points.")
        points = frame[[x_column, y_column]].to_numpy(dtype=float)
        if np.linalg.matrix_rank(points - points.mean(axis=0)) < 2:
            raise ValueError("Contour and surface charts need non-collinear X/Y points.")
        try:
            triangulation = mtri.Triangulation(frame[x_column], frame[y_column])
        except (RuntimeError, ValueError) as exc:
            raise ValueError("The X/Y points cannot form a valid triangulation.") from exc
        return frame, triangulation

    def _colors(self, settings: PlotSettings) -> list[str]:
        return PALETTES.get(settings.palette, PALETTES["SciPlot Classic"])

    def _plot(self, axes: Any, chart_type: str, settings: PlotSettings) -> None:
        handlers = {
            "line": lambda: self._plot_xy(axes, settings, "line"),
            "step": lambda: self._plot_xy(axes, settings, "step"),
            "scatter": lambda: self._plot_xy(axes, settings, "scatter"),
            "area": lambda: self._plot_area(axes, settings, False),
            "stacked_area": lambda: self._plot_area(axes, settings, True),
            "bubble": lambda: self._plot_bubble(axes, settings),
            "bar": lambda: self._plot_bar(axes, settings, False),
            "barh": lambda: self._plot_bar(axes, settings, True),
            "errorbar": lambda: self._plot_errorbar(axes, settings),
            "histogram": lambda: self._plot_histogram(axes, settings),
            "density": lambda: self._plot_density(axes, settings),
            "ecdf": lambda: self._plot_ecdf(axes, settings),
            "boxplot": lambda: self._plot_boxplot(axes, settings),
            "violin": lambda: self._plot_violin(axes, settings),
            "stem": lambda: self._plot_stem(axes, settings),
            "lollipop": lambda: self._plot_lollipop(axes, settings),
            "heatmap": lambda: self._plot_heatmap(axes, settings),
            "hist2d": lambda: self._plot_hist2d(axes, settings),
            "hexbin": lambda: self._plot_hexbin(axes, settings),
            "contour": lambda: self._plot_contour(axes, settings, False),
            "contourf": lambda: self._plot_contour(axes, settings, True),
            "radar": lambda: self._plot_radar(axes, settings),
            "polar_line": lambda: self._plot_polar(axes, settings, False),
            "polar_scatter": lambda: self._plot_polar(axes, settings, True),
            "pie": lambda: self._plot_pie(axes, settings, False),
            "donut": lambda: self._plot_pie(axes, settings, True),
        }
        if chart_type in THREE_D_CHARTS:
            self._plot_3d(axes, settings)
        else:
            handlers[chart_type]()

    def _plot_xy(self, axes: Any, settings: PlotSettings, mode: str) -> None:
        colors = self._colors(settings)
        groups: list[tuple[Any, pd.DataFrame]] = [(None, self.dataframe)]
        if settings.group_col:
            groups = list(self.dataframe.groupby(settings.group_col, dropna=True, sort=False))
        y_columns = settings.y_cols or []
        for group_index, (group_name, group_frame) in enumerate(groups):
            for y_index, y_column in enumerate(y_columns):
                x, y = self._xy_frame(settings.x_col, y_column, settings, group_frame)
                if y.empty:
                    continue
                label = y_column if group_name is None else f"{group_name} - {y_column}"
                color = colors[(group_index * len(y_columns) + y_index) % len(colors)]
                if mode == "line":
                    axes.plot(x, y, label=label, color=color, linewidth=settings.line_width, linestyle=settings.line_style, marker=settings.marker or None, markersize=settings.marker_size)
                elif mode == "step":
                    axes.step(x, y, label=label, color=color, linewidth=settings.line_width, linestyle=settings.line_style, where="mid")
                else:
                    axes.scatter(x, y, label=label, color=color, s=max(4, settings.marker_size**2), alpha=0.82)

    def _plot_area(self, axes: Any, settings: PlotSettings, stacked: bool) -> None:
        colors = self._colors(settings)
        y_columns = settings.y_cols or []
        if stacked:
            columns = [settings.x_col, *y_columns]
            frame = self.dataframe[columns].copy()
            x_numeric = pd.to_numeric(frame[settings.x_col], errors="coerce")
            if x_numeric.notna().sum() >= max(1, int(frame[settings.x_col].notna().sum() * 0.6)):
                frame[settings.x_col] = x_numeric
            for column in y_columns:
                frame[column] = pd.to_numeric(frame[column], errors="coerce")
            if settings.missing_policy == "zero":
                frame[y_columns] = frame[y_columns].fillna(0)
            elif settings.missing_policy == "interpolate":
                frame[y_columns] = frame[y_columns].interpolate(limit_direction="both")
            frame = frame.dropna(subset=columns)
            if settings.sort_x:
                frame = frame.sort_values(settings.x_col)
            axes.stackplot(frame[settings.x_col], *[frame[column] for column in y_columns], labels=y_columns, colors=colors[: len(y_columns)], alpha=0.78)
            return
        groups: list[tuple[Any, pd.DataFrame]] = [(None, self.dataframe)]
        if settings.group_col:
            groups = list(self.dataframe.groupby(settings.group_col, dropna=True, sort=False))
        for group_index, (group_name, group_frame) in enumerate(groups):
            for y_index, column in enumerate(y_columns):
                x, y = self._xy_frame(settings.x_col, column, settings, group_frame)
                if y.empty:
                    continue
                label = column if group_name is None else f"{group_name} - {column}"
                color = colors[(group_index * len(y_columns) + y_index) % len(colors)]
                axes.plot(x, y, label=label, color=color, linewidth=settings.line_width)
                axes.fill_between(x, y, alpha=0.22, color=color)

    def _plot_bubble(self, axes: Any, settings: PlotSettings) -> None:
        y_column = (settings.y_cols or [""])[0]
        columns = [settings.x_col, y_column, settings.size_col, settings.color_col]
        frame = self._numeric_frame(columns, settings)
        if frame.empty:
            raise ValueError("The bubble chart has no complete numeric rows.")
        if settings.size_col:
            values = frame[settings.size_col]
            span = values.max() - values.min()
            sizes = np.full(len(frame), 55.0) if span == 0 else 25 + (values - values.min()) / span * 220
        else:
            sizes = max(40, settings.marker_size**2)
        kwargs: dict[str, Any] = {"color": self._colors(settings)[0]}
        if settings.color_col:
            kwargs = {"c": frame[settings.color_col], "cmap": "viridis"}
        artist = axes.scatter(frame[settings.x_col], frame[y_column], s=sizes, alpha=0.72, edgecolors="#ffffff", linewidths=0.6, label=y_column, **kwargs)
        if settings.color_col:
            axes.figure.colorbar(artist, ax=axes, fraction=0.046, pad=0.04, label=settings.color_col)

    def _plot_bar(self, axes: Any, settings: PlotSettings, horizontal: bool) -> None:
        colors = self._colors(settings)
        y_columns = settings.y_cols or []
        series: list[tuple[str, pd.Series]] = []
        if settings.group_col:
            columns = [settings.x_col, settings.group_col, *y_columns]
            frame = self.dataframe[columns].dropna(subset=[settings.x_col, settings.group_col]).copy()
            if frame.duplicated([settings.x_col, settings.group_col]).any():
                raise ValueError("Grouped bar charts require one row per X/group combination. Aggregate duplicate rows first.")
            categories = list(pd.unique(frame[settings.x_col]))
            if settings.sort_x:
                try:
                    categories = sorted(categories)
                except TypeError:
                    pass
            groups = list(pd.unique(frame[settings.group_col]))
            for group in groups:
                group_frame = frame.loc[frame[settings.group_col] == group].set_index(settings.x_col)
                for column in y_columns:
                    values = pd.to_numeric(group_frame[column], errors="coerce").reindex(categories)
                    if settings.missing_policy == "zero":
                        values = values.fillna(0)
                    elif settings.missing_policy == "interpolate":
                        values = values.interpolate(limit_direction="both")
                    series.append((f"{group} - {column}", values))
            labels = pd.Series([str(value) for value in categories])
        else:
            labels = self.dataframe[settings.x_col].astype(str)
            for column in y_columns:
                values = self._numeric(column)
                if settings.missing_policy == "zero":
                    values = values.fillna(0)
                elif settings.missing_policy == "interpolate":
                    values = values.interpolate(limit_direction="both")
                series.append((column, values))
        indices = np.arange(len(labels))
        thickness = min(0.8 / max(len(series), 1), 0.35)
        for index, (label, values) in enumerate(series):
            offset = (index - (len(series) - 1) / 2) * thickness
            if horizontal:
                axes.barh(indices + offset, values, height=thickness, label=label, color=colors[index % len(colors)])
            else:
                axes.bar(indices + offset, values, width=thickness, label=label, color=colors[index % len(colors)])
        if horizontal:
            axes.set_yticks(indices)
            axes.set_yticklabels(labels)
            axes.invert_yaxis()
        else:
            axes.set_xticks(indices)
            axes.set_xticklabels(labels)

    def _plot_errorbar(self, axes: Any, settings: PlotSettings) -> None:
        y_column = (settings.y_cols or [""])[0]
        groups: list[tuple[Any, pd.DataFrame]] = [(None, self.dataframe)]
        if settings.group_col:
            groups = list(self.dataframe.groupby(settings.group_col, dropna=True, sort=False))
        colors = self._colors(settings)
        for index, (group_name, group_frame) in enumerate(groups):
            frame = group_frame[[settings.x_col, y_column, settings.error_col]].copy()
            frame[y_column] = pd.to_numeric(frame[y_column], errors="coerce")
            frame[settings.error_col] = pd.to_numeric(frame[settings.error_col], errors="coerce")
            if settings.missing_policy == "zero":
                frame[[y_column, settings.error_col]] = frame[[y_column, settings.error_col]].fillna(0)
            elif settings.missing_policy == "interpolate":
                frame[[y_column, settings.error_col]] = frame[[y_column, settings.error_col]].interpolate(limit_direction="both")
            frame = frame.dropna()
            if settings.sort_x:
                try:
                    frame = frame.sort_values(settings.x_col)
                except TypeError:
                    pass
            if (frame[settings.error_col] < 0).any():
                raise ValueError("Error values must be non-negative.")
            label = y_column if group_name is None else f"{group_name} - {y_column}"
            axes.errorbar(frame[settings.x_col], frame[y_column], yerr=frame[settings.error_col], label=label, color=colors[index % len(colors)], linewidth=settings.line_width, marker=settings.marker or "o", markersize=settings.marker_size, capsize=4)

    def _plot_histogram(self, axes: Any, settings: PlotSettings) -> None:
        colors = self._colors(settings)
        for index, column in enumerate(settings.y_cols or []):
            values = self._numeric(column).dropna()
            axes.hist(values, bins=settings.bins, alpha=0.62, label=column, color=colors[index % len(colors)])

    def _plot_density(self, axes: Any, settings: PlotSettings) -> None:
        from scipy.stats import gaussian_kde

        colors = self._colors(settings)
        for index, column in enumerate(settings.y_cols or []):
            values = self._numeric(column).dropna().to_numpy(dtype=float)
            if values.size < 2:
                continue
            color = colors[index % len(colors)]
            if np.allclose(values, values[0]):
                axes.axvline(values[0], label=column, color=color, linewidth=settings.line_width)
                continue
            if values.size > 10000:
                values = np.random.default_rng(0).choice(values, 10000, replace=False)
            estimator = gaussian_kde(values)
            padding = max(np.std(values) * 0.5, (values.max() - values.min()) * 0.05)
            x_values = np.linspace(values.min() - padding, values.max() + padding, max(200, settings.bins * 8))
            density = estimator(x_values)
            axes.plot(x_values, density, label=column, color=color, linewidth=settings.line_width)
            axes.fill_between(x_values, density, color=color, alpha=0.16)

    def _plot_ecdf(self, axes: Any, settings: PlotSettings) -> None:
        colors = self._colors(settings)
        for index, column in enumerate(settings.y_cols or []):
            values = np.sort(self._numeric(column).dropna().to_numpy())
            if values.size:
                axes.step(values, np.arange(1, values.size + 1) / values.size, where="post", label=column, color=colors[index % len(colors)], linewidth=settings.line_width)

    def _plot_boxplot(self, axes: Any, settings: PlotSettings) -> None:
        columns = settings.y_cols or []
        data = [self._numeric(column).dropna() for column in columns]
        box = axes.boxplot(data, tick_labels=columns, patch_artist=True)
        colors = self._colors(settings)
        for index, patch in enumerate(box["boxes"]):
            patch.set_facecolor(colors[index % len(colors)])
            patch.set_alpha(0.6)

    def _plot_violin(self, axes: Any, settings: PlotSettings) -> None:
        columns = settings.y_cols or []
        data = [self._numeric(column).dropna() for column in columns]
        if any(len(values) == 0 for values in data):
            raise ValueError("Every selected violin series needs numeric values.")
        violin = axes.violinplot(data, showmeans=True, showextrema=True)
        colors = self._colors(settings)
        for index, body in enumerate(violin["bodies"]):
            body.set_facecolor(colors[index % len(colors)])
            body.set_edgecolor("#374151")
            body.set_alpha(0.55)
        axes.set_xticks(range(1, len(columns) + 1))
        axes.set_xticklabels(columns)

    def _plot_stem(self, axes: Any, settings: PlotSettings) -> None:
        x = self._numeric(settings.x_col)
        colors = self._colors(settings)
        for index, column in enumerate(settings.y_cols or []):
            markerline, stemlines, baseline = axes.stem(x, self._numeric(column), label=column)
            color = colors[index % len(colors)]
            markerline.set_color(color)
            stemlines.set_color(color)
            baseline.set_color("#9ca3af")

    def _plot_lollipop(self, axes: Any, settings: PlotSettings) -> None:
        labels = self.dataframe[settings.x_col].astype(str)
        indices = np.arange(len(labels))
        colors = self._colors(settings)
        for index, column in enumerate(settings.y_cols or []):
            values = self._numeric(column)
            color = colors[index % len(colors)]
            axes.vlines(indices, 0, values, color=color, alpha=0.7, linewidth=settings.line_width)
            axes.scatter(indices, values, color=color, s=max(30, settings.marker_size**2), label=column, zorder=3)
        axes.set_xticks(indices)
        axes.set_xticklabels(labels)

    def _plot_heatmap(self, axes: Any, settings: PlotSettings) -> None:
        columns = settings.y_cols or [str(column) for column in self.dataframe.select_dtypes(include="number").columns]
        if len(columns) < 2:
            raise ValueError("A correlation heatmap needs at least two numeric columns.")
        correlation = self.dataframe[columns].apply(pd.to_numeric, errors="coerce").corr()
        image = axes.imshow(correlation.values, cmap="coolwarm", vmin=-1, vmax=1)
        axes.set_xticks(range(len(columns)))
        axes.set_yticks(range(len(columns)))
        axes.set_xticklabels(columns)
        axes.set_yticklabels(columns)
        for row in range(len(columns)):
            for column in range(len(columns)):
                value = correlation.values[row, column]
                color = "white" if np.isfinite(value) and abs(value) > 0.55 else "#111827"
                axes.text(column, row, "-" if not np.isfinite(value) else f"{value:.2f}", ha="center", va="center", color=color, fontsize=max(7, settings.font_size - 2))
        axes.figure.colorbar(image, ax=axes, fraction=0.046, pad=0.04, label="Pearson r")

    def _plot_hist2d(self, axes: Any, settings: PlotSettings) -> None:
        y_column = (settings.y_cols or [""])[0]
        frame = self._numeric_frame([settings.x_col, y_column], settings)
        image = axes.hist2d(frame[settings.x_col], frame[y_column], bins=settings.bins, cmap="viridis")
        axes.figure.colorbar(image[3], ax=axes, fraction=0.046, pad=0.04, label="Count")

    def _plot_hexbin(self, axes: Any, settings: PlotSettings) -> None:
        y_column = (settings.y_cols or [""])[0]
        frame = self._numeric_frame([settings.x_col, y_column], settings)
        artist = axes.hexbin(frame[settings.x_col], frame[y_column], gridsize=settings.bins, cmap="viridis", mincnt=1)
        axes.figure.colorbar(artist, ax=axes, fraction=0.046, pad=0.04, label="Count")

    def _plot_contour(self, axes: Any, settings: PlotSettings, filled: bool) -> None:
        y_column = (settings.y_cols or [""])[0]
        frame, triangulation = self._triangulation(settings.x_col, y_column, settings.z_col, settings)
        if filled:
            artist = axes.tricontourf(triangulation, frame[settings.z_col], levels=min(settings.bins, 40), cmap="viridis")
        else:
            artist = axes.tricontour(triangulation, frame[settings.z_col], levels=min(settings.bins, 40), cmap="viridis", linewidths=1.0)
            axes.clabel(artist, inline=True, fontsize=max(7, settings.font_size - 2))
        axes.figure.colorbar(artist, ax=axes, fraction=0.046, pad=0.04, label=settings.z_col)

    def _plot_radar(self, axes: Any, settings: PlotSettings) -> None:
        columns = settings.y_cols or []
        if len(columns) < 3:
            raise ValueError("A radar chart needs at least three Y columns.")
        values = np.asarray([self._numeric(column).mean(skipna=True) for column in columns], dtype=float)
        if not np.isfinite(values).all():
            raise ValueError("Every radar axis needs at least one numeric value.")
        if settings.radar_normalize:
            minima = np.asarray([self._numeric(column).min(skipna=True) for column in columns], dtype=float)
            maxima = np.asarray([self._numeric(column).max(skipna=True) for column in columns], dtype=float)
            span = maxima - minima
            values = np.where(span > 0, (values - minima) / span, 1.0)
        angles = np.linspace(0, 2 * np.pi, len(columns), endpoint=False)
        closed_angles = np.append(angles, angles[0])
        closed_values = np.append(values, values[0])
        color = self._colors(settings)[0]
        axes.plot(closed_angles, closed_values, color=color, linewidth=settings.line_width, marker=settings.marker or "o")
        axes.fill(closed_angles, closed_values, color=color, alpha=0.18)
        axes.set_xticks(angles)
        axes.set_xticklabels(columns)

    def _plot_polar(self, axes: Any, settings: PlotSettings, scatter: bool) -> None:
        theta = self._numeric(settings.x_col)
        if settings.polar_degrees:
            theta = np.deg2rad(theta)
        colors = self._colors(settings)
        for index, column in enumerate(settings.y_cols or []):
            radius = self._numeric(column)
            valid = theta.notna() & radius.notna()
            color = colors[index % len(colors)]
            if scatter:
                axes.scatter(theta[valid], radius[valid], label=column, color=color, s=max(20, settings.marker_size**2))
            else:
                axes.plot(theta[valid], radius[valid], label=column, color=color, linewidth=settings.line_width, marker=settings.marker or None)

    def _plot_pie(self, axes: Any, settings: PlotSettings, donut: bool) -> None:
        y_column = (settings.y_cols or [""])[0]
        if not y_column:
            raise ValueError("Select a value column for the pie chart.")
        values = self._numeric(y_column)
        if settings.x_col:
            frame = pd.DataFrame({"label": self.dataframe[settings.x_col].astype(str), "value": values}).dropna()
            grouped = frame.groupby("label", sort=False)["value"].sum()
            labels = grouped.index.tolist()
            data = grouped.to_numpy(dtype=float)
        else:
            data = values.dropna().to_numpy(dtype=float)
            labels = [str(index + 1) for index in range(len(data))]
        if np.any(data < 0):
            raise ValueError("Pie-chart values must be non-negative.")
        if data.size == 0 or float(data.sum()) <= 0:
            raise ValueError("Pie-chart values must have a positive total.")
        colors = self._colors(settings)
        axes.pie(data, labels=labels, autopct="%1.1f%%", colors=(colors * ((len(data) // len(colors)) + 1))[: len(data)], startangle=90)
        if donut:
            axes.add_artist(Circle((0, 0), 0.58, fc="white"))
        axes.axis("equal")

    def _plot_3d(self, axes: Any, settings: PlotSettings) -> None:
        y_column = (settings.y_cols or [""])[0]
        frame = self._numeric_frame([settings.x_col, y_column, settings.z_col], settings)
        if frame.empty:
            raise ValueError("The 3D chart has no complete numeric X/Y/Z rows.")
        if settings.sort_x:
            frame = frame.sort_values(settings.x_col)
        x = frame[settings.x_col]
        y = frame[y_column]
        z = frame[settings.z_col]
        colors = self._colors(settings)
        axes.view_init(elev=settings.elev, azim=settings.azim)
        if settings.chart_type == "scatter3d":
            color_values = z
            if settings.color_col:
                color_values = pd.to_numeric(self.dataframe.loc[frame.index, settings.color_col], errors="coerce").fillna(z)
            artist = axes.scatter(x, y, z, c=color_values, cmap="viridis", s=max(25, settings.marker_size**2), depthshade=True)
            axes.figure.colorbar(artist, ax=axes, fraction=0.046, pad=0.04, label=settings.color_col or settings.z_col)
        elif settings.chart_type == "line3d":
            axes.plot(x, y, z, color=colors[0], linewidth=settings.line_width, marker=settings.marker or None, label=y_column)
        elif settings.chart_type in {"surface3d", "wireframe3d", "contour3d"}:
            surface_frame, triangulation = self._triangulation(settings.x_col, y_column, settings.z_col, settings)
            surface_z = surface_frame[settings.z_col]
            if settings.chart_type == "surface3d":
                artist = axes.plot_trisurf(triangulation, surface_z, cmap="viridis", alpha=0.88, linewidth=0.25)
                axes.figure.colorbar(artist, ax=axes, fraction=0.046, pad=0.04, label=settings.z_col)
            elif settings.chart_type == "wireframe3d":
                artist = axes.plot_trisurf(triangulation, surface_z, color=colors[0], alpha=0.0, edgecolor=colors[0], linewidth=0.7)
                artist.set_facecolor((0, 0, 0, 0))
            else:
                axes.tricontour(triangulation, surface_z, levels=min(settings.bins, 35), cmap="viridis")
        else:
            def spacing(values: pd.Series) -> float:
                unique = np.sort(values.unique())
                diffs = np.diff(unique)
                return float(np.median(diffs[diffs > 0]) * 0.6) if np.any(diffs > 0) else 0.45
            dx = np.full(len(frame), spacing(x))
            dy = np.full(len(frame), spacing(y))
            axes.bar3d(x - dx / 2, y - dy / 2, np.zeros(len(frame)), dx, dy, z, color=colors[0], alpha=0.72, shade=True)

    def _decorate(self, axes: Any, figure: Figure, settings: PlotSettings) -> dict[str, Any]:
        title = axes.set_title(settings.title, fontsize=settings.font_size + 2, pad=settings.title_pad, wrap=True)
        title.set_picker(True)
        if settings.title_x is not None and settings.title_y is not None:
            title.set_position((settings.title_x, settings.title_y))

        if settings.chart_type in THREE_D_CHARTS:
            axes.set_xlabel(settings.xlabel or settings.x_col, labelpad=settings.axis_label_pad)
            axes.set_ylabel(settings.ylabel or ", ".join(settings.y_cols or []), labelpad=settings.axis_label_pad)
            axes.set_zlabel(settings.zlabel or settings.z_col, labelpad=settings.axis_label_pad)
        elif settings.chart_type not in {"heatmap", "radar", "polar_line", "polar_scatter", "pie", "donut"}:
            axes.set_xlabel(settings.xlabel or settings.x_col, labelpad=settings.axis_label_pad)
            axes.set_ylabel(settings.ylabel or ", ".join(settings.y_cols or []), labelpad=settings.axis_label_pad)
        xlabel = axes.xaxis.label
        ylabel = axes.yaxis.label
        xlabel.set_picker(True)
        ylabel.set_picker(True)
        if settings.xlabel_x is not None and settings.xlabel_y is not None:
            axes.xaxis.set_label_coords(settings.xlabel_x, settings.xlabel_y)
        if settings.ylabel_x is not None and settings.ylabel_y is not None:
            axes.yaxis.set_label_coords(settings.ylabel_x, settings.ylabel_y)

        axes.tick_params(axis="both", pad=settings.tick_label_pad)
        if settings.grid and settings.chart_type not in {"heatmap", "pie", "donut"}:
            axes.grid(True, color="#d1d5db", linewidth=0.7, alpha=0.75)

        legend = None
        if settings.legend and settings.legend_position != "none" and settings.chart_type not in {"heatmap", "pie", "donut"}:
            handles, labels = axes.get_legend_handles_labels()
            if handles:
                if settings.legend_x is not None and settings.legend_y is not None:
                    legend = axes.legend(frameon=False, loc="center", bbox_to_anchor=(settings.legend_x, settings.legend_y), fontsize=max(8, settings.font_size - 1))
                elif settings.legend_position == "right":
                    legend = axes.legend(frameon=False, loc="center left", bbox_to_anchor=(1.02, 0.5), fontsize=max(8, settings.font_size - 1))
                elif settings.legend_position == "bottom":
                    legend = axes.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.16), ncol=min(3, len(labels)), fontsize=max(8, settings.font_size - 1))
                elif settings.legend_position == "upper_left":
                    legend = axes.legend(frameon=False, loc="upper left", fontsize=max(8, settings.font_size - 1))
                elif settings.legend_position == "upper_right":
                    legend = axes.legend(frameon=False, loc="upper right", fontsize=max(8, settings.font_size - 1))
                else:
                    legend = axes.legend(frameon=False, loc="best", fontsize=max(8, settings.font_size - 1))
                if legend is not None:
                    legend.set_picker(True)

        if hasattr(axes, "spines"):
            for spine in axes.spines.values():
                spine.set_color("#374151")
                spine.set_linewidth(0.8)

        if settings.chart_type not in {"heatmap", "radar", "polar_line", "polar_scatter", "pie", "donut"}:
            ticks = [tick for tick in axes.get_xticklabels() if tick.get_text()]
            rotation = settings.x_tick_rotation or (30 if len(ticks) > 8 else 0)
            for tick in ticks:
                tick.set_rotation(rotation)
                tick.set_ha("right" if rotation else "center")

        if settings.chart_type not in THREE_D_CHARTS | POLAR_CHARTS | {"pie", "donut"}:
            axes.set_xscale(settings.x_scale)
            axes.set_yscale(settings.y_scale)
            if settings.x_min is not None or settings.x_max is not None:
                axes.set_xlim(left=settings.x_min, right=settings.x_max)
            if settings.y_min is not None or settings.y_max is not None:
                axes.set_ylim(bottom=settings.y_min, top=settings.y_max)

        manual_requested = any(value > 0 for value in (settings.margin_left, settings.margin_right, settings.margin_top, settings.margin_bottom))
        outside_legend = legend is not None and settings.legend_position in {"right", "bottom"}
        if settings.tight_layout and settings.chart_type in THREE_D_CHARTS:
            figure.set_layout_engine(None)
            figure.subplots_adjust(left=0.03, right=0.90, top=0.88, bottom=0.07)
        elif settings.tight_layout and not manual_requested and not outside_legend:
            figure.set_layout_engine("tight", pad=1.5)
        elif settings.tight_layout:
            try:
                with warnings.catch_warnings():
                    warnings.filterwarnings("error", message="Tight layout not applied.*")
                    figure.tight_layout(pad=1.5)
            except Warning:
                figure.subplots_adjust(left=0.13, right=0.91, top=0.87, bottom=0.15)
        if settings.legend_position == "bottom" and legend is not None:
            figure.subplots_adjust(bottom=0.27)
        manual: dict[str, float] = {}
        if settings.margin_left > 0:
            manual["left"] = settings.margin_left
        if settings.margin_right > 0:
            manual["right"] = 1 - settings.margin_right
        if settings.margin_top > 0:
            manual["top"] = 1 - settings.margin_top
        if settings.margin_bottom > 0:
            manual["bottom"] = settings.margin_bottom
        if manual:
            figure.subplots_adjust(**manual)
        return {"title": title, "xlabel": xlabel, "ylabel": ylabel, "legend": legend, "axes": axes}


def save_figure(dataframe: pd.DataFrame, settings: PlotSettings, path: str, dpi: int, transparent: bool = False) -> None:
    output = Path(path).expanduser()
    pixel_count = settings.width * dpi * settings.height * dpi
    if output.suffix.lower() == ".png" and pixel_count > 120_000_000:
        raise ValueError("The requested PNG is too large. Reduce dimensions or DPI.")
    output.parent.mkdir(parents=True, exist_ok=True)
    figure = PlotEngine(dataframe).create_figure(settings, dpi=dpi)
    try:
        figure.savefig(output, dpi=dpi, transparent=transparent, facecolor="none" if transparent else figure.get_facecolor())
    finally:
        figure.clear()
