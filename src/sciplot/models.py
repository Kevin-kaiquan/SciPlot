from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from typing import Any


CHART_DEFINITIONS: dict[str, dict[str, str]] = {
    "line": {"en": "Line", "zh_TW": "折線圖", "zh_CN": "折线图"},
    "step": {"en": "Step", "zh_TW": "階梯圖", "zh_CN": "阶梯图"},
    "area": {"en": "Area", "zh_TW": "面積圖", "zh_CN": "面积图"},
    "stacked_area": {"en": "Stacked area", "zh_TW": "堆疊面積圖", "zh_CN": "堆叠面积图"},
    "scatter": {"en": "Scatter", "zh_TW": "散點圖", "zh_CN": "散点图"},
    "bubble": {"en": "Bubble", "zh_TW": "氣泡圖", "zh_CN": "气泡图"},
    "bar": {"en": "Bar", "zh_TW": "柱狀圖", "zh_CN": "柱状图"},
    "barh": {"en": "Horizontal bar", "zh_TW": "水平柱狀圖", "zh_CN": "水平柱状图"},
    "errorbar": {"en": "Error bar", "zh_TW": "誤差棒", "zh_CN": "误差棒"},
    "histogram": {"en": "Histogram", "zh_TW": "直方圖", "zh_CN": "直方图"},
    "density": {"en": "Kernel density", "zh_TW": "核密度曲線", "zh_CN": "核密度曲线"},
    "ecdf": {"en": "ECDF", "zh_TW": "累積分布 ECDF", "zh_CN": "累积分布 ECDF"},
    "boxplot": {"en": "Box plot", "zh_TW": "箱線圖", "zh_CN": "箱线图"},
    "violin": {"en": "Violin", "zh_TW": "小提琴圖", "zh_CN": "小提琴图"},
    "stem": {"en": "Stem", "zh_TW": "莖葉圖 Stem", "zh_CN": "茎叶图 Stem"},
    "lollipop": {"en": "Lollipop", "zh_TW": "棒棒糖圖", "zh_CN": "棒棒糖图"},
    "heatmap": {"en": "Correlation heatmap", "zh_TW": "相關熱圖", "zh_CN": "相关热图"},
    "hist2d": {"en": "2D histogram", "zh_TW": "二維直方圖", "zh_CN": "二维直方图"},
    "hexbin": {"en": "Hexbin density", "zh_TW": "六邊形密度圖", "zh_CN": "六边形密度图"},
    "contour": {"en": "Contour", "zh_TW": "等高線圖", "zh_CN": "等高线图"},
    "contourf": {"en": "Filled contour", "zh_TW": "填色等高線圖", "zh_CN": "填色等高线图"},
    "radar": {"en": "Radar", "zh_TW": "雷達圖", "zh_CN": "雷达图"},
    "polar_line": {"en": "Polar line", "zh_TW": "極坐標折線圖", "zh_CN": "极坐标折线图"},
    "polar_scatter": {"en": "Polar scatter", "zh_TW": "極坐標散點圖", "zh_CN": "极坐标散点图"},
    "pie": {"en": "Pie", "zh_TW": "餅圖", "zh_CN": "饼图"},
    "donut": {"en": "Donut", "zh_TW": "環形圖", "zh_CN": "环形图"},
    "scatter3d": {"en": "3D scatter", "zh_TW": "3D 散點圖", "zh_CN": "3D 散点图"},
    "line3d": {"en": "3D line", "zh_TW": "3D 折線圖", "zh_CN": "3D 折线图"},
    "surface3d": {"en": "3D surface", "zh_TW": "3D 曲面圖", "zh_CN": "3D 曲面图"},
    "wireframe3d": {"en": "3D wireframe", "zh_TW": "3D 網格圖", "zh_CN": "3D 网格图"},
    "bar3d": {"en": "3D bar", "zh_TW": "3D 柱狀圖", "zh_CN": "3D 柱状图"},
    "contour3d": {"en": "3D contour", "zh_TW": "3D 等高線圖", "zh_CN": "3D 等高线图"},
}

LEGACY_CHART_NAMES = {
    definition[language]: chart_id
    for chart_id, definition in CHART_DEFINITIONS.items()
    for language in ("en", "zh_TW", "zh_CN")
}

CHART_GROUPS: dict[str, tuple[str, ...]] = {
    "core": ("line", "step", "area", "stacked_area", "scatter", "bubble", "bar", "barh", "errorbar"),
    "distribution": ("histogram", "density", "ecdf", "boxplot", "violin", "stem", "lollipop"),
    "matrix": ("heatmap", "hist2d", "hexbin", "contour", "contourf"),
    "polar": ("radar", "polar_line", "polar_scatter", "pie", "donut"),
    "3d": ("scatter3d", "line3d", "surface3d", "wireframe3d", "bar3d", "contour3d"),
}

PALETTES = {
    "SciPlot Classic": ["#2563eb", "#ef4444", "#111827", "#60a5fa", "#f59e0b", "#10b981"],
    "Journal": ["#1f5f8b", "#c44e52", "#55a868", "#8172b3", "#ccb974", "#64b5cd"],
    "Colorblind": ["#0072B2", "#D55E00", "#009E73", "#CC79A7", "#F0E442", "#56B4E9"],
    "Monochrome": ["#111827", "#374151", "#6b7280", "#9ca3af", "#d1d5db", "#4b5563"],
    "Warm": ["#8c2d04", "#cc4c02", "#ec7014", "#fe9929", "#fec44f", "#fff7bc"],
    "Cool contrast": ["#003f5c", "#2f4b7c", "#665191", "#a05195", "#d45087", "#f95d6a"],
}

LEGACY_PALETTES = {
    "期刊藍灰": "Journal",
    "期刊蓝灰": "Journal",
    "色盲友好": "Colorblind",
    "單色灰階": "Monochrome",
    "单色灰阶": "Monochrome",
    "實驗室暖色": "Warm",
    "实验室暖色": "Warm",
    "對比冷色": "Cool contrast",
    "对比冷色": "Cool contrast",
}

LEGACY_LEGEND_POSITIONS = {
    "自動": "auto",
    "自动": "auto",
    "右上": "upper_right",
    "左上": "upper_left",
    "右側": "right",
    "右侧": "right",
    "底部": "bottom",
    "無": "none",
    "无": "none",
}

COLORBAR_POSITIONS = {"auto", "right", "left", "top", "bottom", "none"}


@dataclass
class PlotSettings:
    chart_type: str = "line"
    x_col: str = ""
    y_cols: list[str] | None = None
    z_col: str = ""
    error_col: str = ""
    group_col: str = ""
    size_col: str = ""
    color_col: str = ""
    title: str = ""
    xlabel: str = ""
    ylabel: str = ""
    zlabel: str = ""
    width: float = 7.2
    height: float = 4.2
    dpi: int = 300
    font_size: int = 10
    line_width: float = 1.8
    marker_size: float = 5.0
    marker: str = "o"
    line_style: str = "-"
    palette: str = "SciPlot Classic"
    grid: bool = True
    legend: bool = True
    tight_layout: bool = True
    title_pad: int = 14
    axis_label_pad: int = 8
    tick_label_pad: int = 4
    x_tick_rotation: int = 0
    legend_position: str = "auto"
    colorbar_position: str = "auto"
    colorbar_pad: float = 0.12
    margin_left: float = 0.0
    margin_right: float = 0.0
    margin_top: float = 0.0
    margin_bottom: float = 0.0
    bins: int = 30
    elev: int = 28
    azim: int = -55
    x_scale: str = "linear"
    y_scale: str = "linear"
    missing_policy: str = "drop"
    sort_x: bool = True
    polar_degrees: bool = True
    radar_normalize: bool = True
    x_min: float | None = None
    x_max: float | None = None
    y_min: float | None = None
    y_max: float | None = None
    title_x: float | None = None
    title_y: float | None = None
    xlabel_x: float | None = None
    xlabel_y: float | None = None
    ylabel_x: float | None = None
    ylabel_y: float | None = None
    legend_x: float | None = None
    legend_y: float | None = None
    colorbar_x: float | None = None
    colorbar_y: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any] | None) -> "PlotSettings":
        payload = dict(value or {})
        chart_value = str(payload.get("chart_type", "line"))
        payload["chart_type"] = LEGACY_CHART_NAMES.get(chart_value, chart_value)
        if payload["chart_type"] not in CHART_DEFINITIONS:
            payload["chart_type"] = "line"
        payload["palette"] = LEGACY_PALETTES.get(str(payload.get("palette", "SciPlot Classic")), payload.get("palette", "SciPlot Classic"))
        payload["legend_position"] = LEGACY_LEGEND_POSITIONS.get(
            str(payload.get("legend_position", "auto")), payload.get("legend_position", "auto")
        )
        colorbar_position = str(payload.get("colorbar_position", "auto"))
        payload["colorbar_position"] = colorbar_position if colorbar_position in COLORBAR_POSITIONS else "auto"
        if payload.get("marker") == "None":
            payload["marker"] = ""
        allowed = {field.name for field in fields(cls)}
        return cls(**{key: item for key, item in payload.items() if key in allowed})


def chart_label(chart_id: str, language: str) -> str:
    definition = CHART_DEFINITIONS.get(chart_id, CHART_DEFINITIONS["line"])
    return definition.get(language, definition["en"])
