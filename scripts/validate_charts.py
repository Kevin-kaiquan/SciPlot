from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pandas as pd
from matplotlib.backend_bases import MouseEvent
from matplotlib.backends.backend_agg import FigureCanvasAgg

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sciplot.data_io import read_data_file  # noqa: E402
from sciplot.drag import LabelDragController  # noqa: E402
from sciplot.i18n import LANGUAGES, TEXT  # noqa: E402
from sciplot.models import CHART_DEFINITIONS, CHART_GROUPS, PlotSettings  # noqa: E402
from sciplot.paths import EXPORT_DIR, SAMPLE_DIR  # noqa: E402
from sciplot.plotting import PlotEngine, save_figure  # noqa: E402
from sciplot.project_io import SessionSourceChangedError, load_project, load_session, save_project, save_session  # noqa: E402
from sciplot.updater import UpdateInfo, _validate_github_https_url, download_update, is_newer_version, preferred_asset  # noqa: E402


def settings_for(chart_type: str, dataframe: pd.DataFrame) -> PlotSettings:
    numeric = [str(column) for column in dataframe.select_dtypes(include="number").columns]
    settings = PlotSettings(
        chart_type=chart_type,
        x_col="time_s" if "time_s" in dataframe.columns else str(dataframe.columns[0]),
        y_cols=["signal_a"] if "signal_a" in dataframe.columns else numeric[1:2] or numeric[:1],
        z_col="temperature_c" if "temperature_c" in dataframe.columns else numeric[2] if len(numeric) > 2 else "",
        error_col="error_a" if "error_a" in dataframe.columns else "",
        group_col="group" if "group" in dataframe.columns and chart_type in {"line", "step", "scatter", "area", "bar", "barh", "errorbar"} else "",
        title=f"SciPlot {chart_type}",
    )
    if chart_type == "bubble":
        settings.size_col = settings.z_col
        settings.color_col = settings.z_col
    if chart_type in {"histogram", "density", "ecdf", "boxplot", "violin", "radar", "heatmap"}:
        settings.y_cols = [column for column in ("signal_a", "signal_b", "signal_c") if column in dataframe.columns] or numeric[:3]
    if chart_type in {"pie", "donut"}:
        settings.x_col = "group" if "group" in dataframe.columns else settings.x_col
        settings.y_cols = ["signal_a"] if "signal_a" in dataframe.columns else numeric[:1]
    if chart_type in {"polar_line", "polar_scatter"}:
        settings.polar_degrees = False
    return settings


def render_all_chart_types() -> None:
    dataframe = read_data_file(SAMPLE_DIR / "example_measurements.csv")
    surface = read_data_file(SAMPLE_DIR / "example_surface_grid.csv")
    failures: list[tuple[str, str]] = []
    surface_types = {"contour", "contourf", "surface3d", "wireframe3d", "contour3d"}
    for chart_type in CHART_DEFINITIONS:
        frame = surface if chart_type in surface_types else dataframe
        settings = settings_for(chart_type, frame)
        if frame is surface:
            settings.x_col = "x"
            settings.y_cols = ["y"]
            settings.z_col = "z"
        try:
            figure = PlotEngine(frame).create_figure(settings, dpi=110)
            output = EXPORT_DIR / f"validate_{chart_type}.png"
            figure.savefig(output, dpi=110)
            if not output.exists() or output.stat().st_size < 1000:
                raise RuntimeError("rendered file is missing or too small")
        except Exception as exc:
            failures.append((chart_type, repr(exc)))
    if failures:
        for chart_type, error in failures:
            print(f"{chart_type}: {error}")
        raise SystemExit(1)


def validate_edge_cases() -> None:
    legacy = PlotSettings.from_dict({"chart_type": "折線圖", "palette": "期刊藍灰", "legend_position": "右側", "marker": "None"})
    if (legacy.chart_type, legacy.palette, legacy.legend_position, legacy.marker) != ("line", "Journal", "right", ""):
        raise RuntimeError("legacy template migration failed")

    frame = pd.DataFrame({"x": [0, 1, 2, 3], "a": [1.0, None, 3.0, 4.0], "b": [2.0, 3.0, 4.0, 5.0], "c": [3.0, 4.0, 5.0, 6.0]})
    settings = PlotSettings(
        chart_type="line",
        x_col="x",
        y_cols=["a", "b"],
        title="Draggable layout",
        title_x=0.4,
        title_y=1.04,
        xlabel_x=0.6,
        xlabel_y=-0.12,
        ylabel_x=-0.14,
        ylabel_y=0.6,
        legend_x=0.78,
        legend_y=0.25,
    )
    figure = PlotEngine(frame).create_figure(settings, dpi=100)
    artists = getattr(figure, "_sciplot_artists", {})
    if set(artists) != {"title", "xlabel", "ylabel", "legend", "axes"}:
        raise RuntimeError("draggable label artists were not registered")

    area = settings_for("area", frame)
    area.x_col = "x"
    area.y_cols = ["a"]
    area.missing_policy = "drop"
    PlotEngine(frame).create_figure(area, dpi=100)

    zero_pie = pd.DataFrame({"label": ["A", "B"], "value": [0, 0]})
    try:
        PlotEngine(zero_pie).create_figure(PlotSettings(chart_type="pie", x_col="label", y_cols=["value"]), dpi=100)
    except ValueError as exc:
        if "positive total" not in str(exc):
            raise
    else:
        raise RuntimeError("zero-total pie chart was not rejected")

    missing = pd.DataFrame({"x": [0, 1, 2], "value": [1.0, None, 3.0]})
    zero_settings = PlotSettings(chart_type="line", x_col="x", y_cols=["value"], missing_policy="zero")
    zero_figure = PlotEngine(missing).create_figure(zero_settings, dpi=100)
    if list(zero_figure.axes[0].lines[0].get_ydata()) != [1.0, 0.0, 3.0]:
        raise RuntimeError("line-chart zero missing-value policy failed")
    interpolate_settings = PlotSettings(chart_type="line", x_col="x", y_cols=["value"], missing_policy="interpolate")
    interpolate_figure = PlotEngine(missing).create_figure(interpolate_settings, dpi=100)
    if list(interpolate_figure.axes[0].lines[0].get_ydata()) != [1.0, 2.0, 3.0]:
        raise RuntimeError("line-chart interpolation policy failed")

    grouped = pd.DataFrame(
        {
            "x": [0, 1, 0, 1],
            "group": ["A", "A", "B", "B"],
            "value": [1.0, 2.0, 3.0, 4.0],
            "error": [0.1, 0.1, 0.2, 0.2],
        }
    )
    for chart_type in ("area", "bar", "errorbar"):
        grouped_settings = PlotSettings(
            chart_type=chart_type,
            x_col="x",
            y_cols=["value"],
            error_col="error",
            group_col="group",
        )
        grouped_figure = PlotEngine(grouped).create_figure(grouped_settings, dpi=100)
        labels = grouped_figure.axes[0].get_legend_handles_labels()[1]
        if labels != ["A - value", "B - value"]:
            raise RuntimeError(f"{chart_type} group handling failed: {labels}")

    with tempfile.TemporaryDirectory(dir=ROOT / "runtime") as directory:
        nested_output = Path(directory) / "new" / "folder" / "exact-size.png"
        export_settings = PlotSettings(chart_type="line", x_col="x", y_cols=["value"], width=4, height=3)
        save_figure(missing.fillna(2), export_settings, str(nested_output), 100)
        from PIL import Image

        with Image.open(nested_output) as image:
            if image.size != (400, 300):
                raise RuntimeError(f"export dimensions changed unexpectedly: {image.size}")


def validate_colorbar_layouts() -> None:
    frame = read_data_file(SAMPLE_DIR / "example_measurements.csv")

    def assert_safe_layout(settings: PlotSettings, context: str) -> None:
        figure = PlotEngine(frame).create_figure(settings, dpi=100)
        canvas = FigureCanvasAgg(figure)
        canvas.draw()
        renderer = canvas.get_renderer()
        artists = getattr(figure, "_sciplot_artists", {})
        axes = artists["axes"]
        colorbar_axes = artists.get("colorbar")
        if colorbar_axes is None:
            raise RuntimeError(f"{context} did not register its colorbar")
        colorbar_bounds = colorbar_axes.get_tightbbox(renderer)
        figure_bounds = figure.bbox
        if (
            colorbar_bounds.x0 < -0.5
            or colorbar_bounds.y0 < -0.5
            or colorbar_bounds.x1 > figure_bounds.x1 + 0.5
            or colorbar_bounds.y1 > figure_bounds.y1 + 0.5
        ):
            raise RuntimeError(f"{context} colorbar was clipped by the figure boundary")
        labels = [axes.title, axes.xaxis.label, axes.yaxis.label]
        if settings.chart_type == "scatter3d":
            labels.append(axes.zaxis.label)
        if any(label.get_text() and label.get_window_extent(renderer).overlaps(colorbar_bounds) for label in labels):
            raise RuntimeError(f"{context} colorbar overlapped an axis label or title")

    for position in ("right", "left", "bottom", "top"):
        for chart_type in ("scatter3d", "heatmap"):
            settings = PlotSettings(
                chart_type=chart_type,
                x_col="time_s" if chart_type == "scatter3d" else "",
                y_cols=["signal_a"] if chart_type == "scatter3d" else ["signal_a", "signal_b", "signal_c"],
                z_col="temperature_c" if chart_type == "scatter3d" else "",
                title=f"{chart_type} colorbar {position}",
                colorbar_position=position,
            )
            assert_safe_layout(settings, f"{chart_type} {position}")

    for width, height in ((7.2, 4.2), (5.0, 5.0), (3.0, 3.0), (2.0, 3.0)):
        responsive = PlotSettings(
            chart_type="scatter3d",
            x_col="time_s",
            y_cols=["signal_a"],
            z_col="temperature_c",
            title="Responsive automatic colorbar",
            width=width,
            height=height,
        )
        assert_safe_layout(responsive, f"scatter3d automatic {width}x{height}")

    manual = PlotSettings(
        chart_type="scatter3d",
        x_col="time_s",
        y_cols=["signal_a"],
        z_col="temperature_c",
        colorbar_position="right",
        colorbar_x=0.22,
        colorbar_y=0.38,
    )
    manual_figure = PlotEngine(frame).create_figure(manual, dpi=100)
    manual_canvas = FigureCanvasAgg(manual_figure)
    manual_canvas.draw()
    colorbar_axes = manual_figure._sciplot_artists["colorbar"]
    bounds = colorbar_axes.get_position()
    if abs(bounds.x0 + bounds.width / 2 - 0.22) > 0.01 or abs(bounds.y0 + bounds.height / 2 - 0.38) > 0.01:
        raise RuntimeError("Manual colorbar position was not restored")

    moved: list[tuple[str, float, float]] = []
    controller = LabelDragController(manual_canvas, lambda name, x, y: moved.append((name, x, y)))
    controller.set_figure(manual_figure)
    controller.set_enabled(True)
    pixel_bounds = colorbar_axes.get_window_extent(manual_canvas.get_renderer())
    press = MouseEvent(
        "button_press_event",
        manual_canvas,
        pixel_bounds.x0 + pixel_bounds.width / 2,
        pixel_bounds.y0 + pixel_bounds.height / 2,
        button=1,
    )
    controller._on_press(press)
    target_x, target_y = manual_figure.transFigure.transform((0.30, 0.45))
    controller._on_motion(MouseEvent("motion_notify_event", manual_canvas, target_x, target_y, button=1))
    controller._on_release(MouseEvent("button_release_event", manual_canvas, target_x, target_y, button=1))
    if not moved or moved[-1][0] != "colorbar" or abs(moved[-1][1] - 0.30) > 0.01 or abs(moved[-1][2] - 0.45) > 0.01:
        raise RuntimeError("Colorbar dragging did not persist the new figure position")

    hidden = PlotSettings(chart_type="heatmap", y_cols=["signal_a", "signal_b"], colorbar_position="none")
    hidden_figure = PlotEngine(frame).create_figure(hidden, dpi=100)
    if "colorbar" in hidden_figure._sciplot_artists or len(hidden_figure.axes) != 1:
        raise RuntimeError("Hidden colorbar still created an axes object")

    with tempfile.TemporaryDirectory(dir=ROOT / "runtime") as directory:
        for suffix in ("png", "svg", "pdf"):
            output = Path(directory) / f"manual-colorbar.{suffix}"
            save_figure(frame, manual, str(output), 120)
            if not output.exists() or output.stat().st_size < 1000:
                raise RuntimeError(f"Manual colorbar {suffix.upper()} export failed")


def validate_project_roundtrip() -> None:
    frame = pd.DataFrame({"when": [pd.Timestamp("2026-01-01"), pd.Timestamp("2026-01-02")], "value": [1.25, 2.5]})
    settings = PlotSettings(
        chart_type="line",
        x_col="when",
        y_cols=["value"],
        title="Datetime roundtrip",
        colorbar_position="bottom",
        colorbar_pad=0.14,
        colorbar_x=0.42,
        colorbar_y=0.18,
    )
    with tempfile.TemporaryDirectory(dir=ROOT / "runtime") as directory:
        path = Path(directory) / "datetime.sciplot"
        save_project(path, frame, settings, r"C:\Users\Example\private.csv")
        project = load_project(path)
        if project.source_name != "private.csv":
            raise RuntimeError("project source path was not sanitized")
        if not pd.api.types.is_datetime64_any_dtype(project.dataframe["when"]):
            raise RuntimeError("datetime project roundtrip failed")
        if (
            project.settings.colorbar_position != "bottom"
            or project.settings.colorbar_pad != 0.14
            or project.settings.colorbar_x != 0.42
            or project.settings.colorbar_y != 0.18
        ):
            raise RuntimeError("colorbar project settings did not roundtrip")


def validate_data_and_session_io() -> None:
    with tempfile.TemporaryDirectory(dir=ROOT / "runtime") as directory:
        root = Path(directory)
        encoded_csv = root / "encoded.csv"
        encoded_csv.write_bytes("時間;信號\n0;1.5\n1;2.5\n".encode("gb18030"))
        encoded = read_data_file(encoded_csv)
        if list(encoded.columns) != ["時間", "信號"] or encoded["信號"].tolist() != [1.5, 2.5]:
            raise RuntimeError("GB18030 delimiter detection failed")

        spreadsheet = root / "measurements.xlsx"
        expected = pd.DataFrame({"time": [0, 1], "signal": [2.5, 3.5]})
        expected.to_excel(spreadsheet, index=False)
        imported = read_data_file(spreadsheet)
        if not imported.equals(expected):
            raise RuntimeError("XLSX import failed")

        source = root / "large.csv"
        large = pd.DataFrame({"x": range(5001), "value": range(5001)})
        large.to_csv(source, index=False)
        session_path = root / "last_session.json"
        settings = PlotSettings(chart_type="line", x_col="x", y_cols=["value"])
        save_session(session_path, large, settings, str(source))
        source.write_text("x,value\n0,999\n", encoding="utf-8")
        try:
            load_session(session_path)
        except SessionSourceChangedError:
            pass
        else:
            raise RuntimeError("Changed large source data was silently restored")

        embedded_path = root / "embedded_session.json"
        save_session(embedded_path, expected, PlotSettings(chart_type="line", x_col="time", y_cols=["signal"]), "")
        embedded = load_session(embedded_path)
        if embedded is None or not embedded.dataframe.equals(expected):
            raise RuntimeError("Embedded session roundtrip failed")


def validate_catalogs() -> None:
    grouped_chart_ids = {chart_id for group in CHART_GROUPS.values() for chart_id in group}
    if grouped_chart_ids != set(CHART_DEFINITIONS):
        raise RuntimeError("Chart groups do not cover the chart catalog exactly")
    for key, translations in TEXT.items():
        missing = set(LANGUAGES) - set(translations)
        if missing:
            raise RuntimeError(f"Missing translations for {key}: {sorted(missing)}")


def validate_updater() -> None:
    if not is_newer_version("3.0.2", "3.0.1") or is_newer_version("2.9.9", "3.0.0"):
        raise RuntimeError("version comparison failed")
    asset = preferred_asset(
        [
            {"name": "SciPlot-macOS-arm64.dmg"},
            {"name": "SciPlot-Windows-x64.msi"},
            {"name": "SciPlot-Windows-x64.zip"},
        ]
    )
    if sys.platform.startswith("win") and (not asset or not str(asset.get("name")).endswith(".msi")):
        raise RuntimeError("Windows updater did not prefer MSI")
    for url in (
        "https://api.github.com/repos/Kevin-kaiquan/SciPlot/releases/latest",
        "https://github.com/Kevin-kaiquan/SciPlot/releases/download/v3.0.0/SciPlot-Windows-x64.msi",
        "https://release-assets.githubusercontent.com/example",
    ):
        _validate_github_https_url(url)
    rejected = UpdateInfo(version="9.9.9", release_url="https://example.com", asset_name="fake.msi", asset_url="https://example.com/fake.msi")
    with tempfile.TemporaryDirectory(dir=ROOT / "runtime") as directory:
        try:
            download_update(rejected, Path(directory) / "fake.msi", lambda _value, _message: None)
        except ValueError as exc:
            if "approved GitHub HTTPS" not in str(exc):
                raise
        else:
            raise RuntimeError("Updater accepted a non-GitHub download URL")


if __name__ == "__main__":
    render_all_chart_types()
    validate_edge_cases()
    validate_colorbar_layouts()
    validate_project_roundtrip()
    validate_data_and_session_io()
    validate_catalogs()
    validate_updater()
    print(f"Validated {len(CHART_DEFINITIONS)} chart types and SciPlot 3 project/update guards.")
