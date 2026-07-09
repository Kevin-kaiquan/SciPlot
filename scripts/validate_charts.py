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

            app.figure = None
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
            app.figure = None
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


def validate_input_guards() -> None:
    app = SciPlotApp(visible=False)
    try:
        gbk_path = EXPORT_DIR / "validate_gb18030_semicolon.csv"
        gbk_path.write_bytes("時間;信號\n0;1.5\n1;2.5\n".encode("gb18030"))
        df = app._read_data_file(gbk_path)
        if list(df.columns) != ["時間", "信號"] or len(df) != 2:
            raise RuntimeError("GB18030 semicolon CSV fallback failed")

        if app._safe_file_stem("CON") != "sciplot_figure":
            raise RuntimeError("reserved Windows filename was not sanitized")
        if "\\" in app._safe_file_stem("bad\\name?.png"):
            raise RuntimeError("unsafe filename separator was not sanitized")
        app.grid_var.set(True)
        app.apply_template({"grid": "False", "width": "not-a-number", "palette": "Missing Palette"})
        if app.grid_var.get():
            raise RuntimeError("template string boolean was not parsed safely")
        if not app._is_newer_version("2.1.5", "2.1.4") or app._is_newer_version("2.1.4", "2.1.5"):
            raise RuntimeError("version comparison failed")
        asset = app._preferred_update_asset(
            [
                {"name": "SciPlot-macOS-arm64.dmg"},
                {"name": "SciPlot-Windows-x64.msi"},
                {"name": "SciPlot-Windows-x64.zip"},
            ]
        )
        if sys.platform.startswith("win") and (not asset or not str(asset.get("name", "")).endswith(".msi")):
            raise RuntimeError("Windows update asset selection failed")

        key_to_label = {value: key for key, value in CHART_TYPES.items()}
        app.df = pd.DataFrame({"x": list(range(8)), "signal_a": range(8), "signal_b": [value * 1.4 for value in range(8)]})
        app.data_source = "manual-layout"
        app.source_var.set(app.data_source)
        app.refresh_after_data_load()
        app.chart_type_var.set(key_to_label["line"])
        app.x_col_var.set("x")
        app._select_y_columns(["signal_a", "signal_b"])
        app.title_var.set("Manual layout validation")
        app.title_pad_var.set(30)
        app.axis_label_pad_var.set(18)
        app.tick_label_pad_var.set(10)
        app.x_tick_rotation_var.set(45)
        app.legend_position_var.set("右側")
        app.margin_right_var.set(0.22)
        app.figure = None
        app.render_plot(silent=True)
        if app.figure is None:
            raise RuntimeError("manual label layout render failed")

        app.df = pd.DataFrame(
            {
                "x": [0, 0, 1, 0, 1],
                "y": [0, 0, 0, 1, 1],
                "z": [1, 3, 2, 4, 5],
            }
        )
        app.data_source = "duplicate-points"
        app.source_var.set(app.data_source)
        app.refresh_after_data_load()
        app.x_col_var.set("x")
        app._select_y_columns(["y"])
        app.z_col_var.set("z")
        for chart_key in ("contour", "surface3d"):
            app.chart_type_var.set(key_to_label[chart_key])
            app.figure = None
            app.render_plot(silent=True)
            if app.figure is None:
                raise RuntimeError(f"{chart_key} duplicate-point render failed")
    finally:
        app.destroy()


if __name__ == "__main__":
    render_all_chart_types()
    render_surface_examples()
    validate_input_guards()
    print(f"Validated {len(CHART_TYPES)} chart types.")
