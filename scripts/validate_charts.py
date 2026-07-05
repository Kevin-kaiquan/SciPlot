from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sciplot_app import CHART_TYPES, EXPORT_DIR, SciPlotApp  # noqa: E402


def render_all_chart_types() -> None:
    app = SciPlotApp(visible=False)
    app.load_sample_data(silent=True)
    numeric = app.numeric_columns()
    failures: list[tuple[str, str, str]] = []

    for chart_type, chart_key in CHART_TYPES.items():
        try:
            app.chart_type_var.set(chart_type)
            if "time_s" in app.df.columns:
                app.x_col_var.set("time_s")
            if "signal_a" in numeric:
                y_cols = ["signal_a", "signal_b"] if "signal_b" in numeric else ["signal_a"]
                app._select_y_columns(y_cols)
            if "temperature_c" in numeric:
                app.z_col_var.set("temperature_c")
            if "error_a" in numeric:
                app.error_col_var.set("error_a")
            app.size_col_var.set("")
            app.color_col_var.set("")

            if chart_key == "bubble":
                app.size_col_var.set("temperature_c")
            if chart_key in {"contour", "contourf", "scatter3d", "line3d", "surface3d", "wireframe3d", "bar3d", "contour3d"}:
                app.x_col_var.set("time_s")
                app._select_y_columns(["signal_a"])
                app.z_col_var.set("temperature_c")
            if chart_key in {"histogram", "density", "ecdf", "boxplot", "violin", "radar", "pie", "donut"}:
                y_cols = ["signal_a", "signal_b", "signal_c"] if "signal_c" in numeric else numeric[:3]
                app._select_y_columns(y_cols)
            if chart_key in {"polar_line", "polar_scatter"}:
                app.x_col_var.set("time_s")
                app._select_y_columns(["signal_a"])

            app.render_plot(silent=True)
            if app.figure is None:
                raise RuntimeError("figure was not rendered")
            output = EXPORT_DIR / f"validate_{chart_key}.png"
            app.figure.savefig(output, dpi=120, bbox_inches="tight")
            if not output.exists() or output.stat().st_size < 1000:
                raise RuntimeError("exported file is too small")
        except Exception as exc:  # pragma: no cover - diagnostic script
            failures.append((chart_type, chart_key, repr(exc)))

    app.destroy()
    if failures:
        for chart_type, chart_key, error in failures:
            print(f"{chart_key} ({chart_type}): {error}")
        raise SystemExit(1)


def render_surface_examples() -> None:
    key_to_label = {value: key for key, value in CHART_TYPES.items()}
    app = SciPlotApp(visible=False)
    app.df = pd.read_csv(ROOT / "sample_data" / "example_surface_grid.csv")
    app.data_source = str(ROOT / "sample_data" / "example_surface_grid.csv")
    app.source_var.set(app.data_source)
    app.refresh_after_data_load()
    app.x_col_var.set("x")
    app._select_y_columns(["y"])
    app.z_col_var.set("z")

    failures: list[tuple[str, str]] = []
    for chart_key in ["contour", "contourf", "scatter3d", "surface3d", "wireframe3d", "contour3d"]:
        try:
            app.chart_type_var.set(key_to_label[chart_key])
            app.render_plot(silent=True)
            output = EXPORT_DIR / f"validate_surface_{chart_key}.png"
            app.figure.savefig(output, dpi=120, bbox_inches="tight")
            if not output.exists() or output.stat().st_size < 1000:
                raise RuntimeError("exported file is too small")
        except Exception as exc:  # pragma: no cover - diagnostic script
            failures.append((chart_key, repr(exc)))

    app.destroy()
    if failures:
        for chart_key, error in failures:
            print(f"{chart_key}: {error}")
        raise SystemExit(1)


if __name__ == "__main__":
    render_all_chart_types()
    render_surface_examples()
    print(f"Validated {len(CHART_TYPES)} chart types.")
