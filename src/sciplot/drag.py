from __future__ import annotations

from collections.abc import Callable
from typing import Any


class LabelDragController:
    def __init__(self, canvas: Any, on_moved: Callable[[str, float, float], None]) -> None:
        self.canvas = canvas
        self.on_moved = on_moved
        self.enabled = False
        self.active: str | None = None
        self.axes: Any = None
        self.artists: dict[str, Any] = {}
        self._connections = [
            canvas.mpl_connect("button_press_event", self._on_press),
            canvas.mpl_connect("motion_notify_event", self._on_motion),
            canvas.mpl_connect("button_release_event", self._on_release),
        ]

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled
        self.active = None

    def set_figure(self, figure: Any) -> None:
        self.axes = getattr(figure, "_sciplot_axes", None)
        self.artists = getattr(figure, "_sciplot_artists", {})

    def _contains(self, artist: Any, event: Any) -> bool:
        if artist is None:
            return False
        try:
            return bool(artist.contains(event)[0])
        except Exception:
            return False

    def _on_press(self, event: Any) -> None:
        if not self.enabled or self.axes is None or event.button != 1:
            return
        for name in ("legend", "title", "xlabel", "ylabel"):
            if self._contains(self.artists.get(name), event):
                self.active = name
                return

    def _axes_position(self, event: Any) -> tuple[float, float] | None:
        if self.axes is None or event.x is None or event.y is None:
            return None
        x, y = self.axes.transAxes.inverted().transform((event.x, event.y))
        return float(x), float(y)

    def _on_motion(self, event: Any) -> None:
        if not self.active:
            return
        position = self._axes_position(event)
        if position is None:
            return
        x, y = position
        if self.active == "title":
            self.artists["title"].set_position((x, y))
        elif self.active == "xlabel":
            self.axes.xaxis.set_label_coords(x, y)
        elif self.active == "ylabel":
            self.axes.yaxis.set_label_coords(x, y)
        elif self.active == "legend":
            legend = self.artists.get("legend")
            if legend is not None:
                legend.set_loc("center")
                legend.set_bbox_to_anchor((x, y), transform=self.axes.transAxes)
        self.canvas.draw_idle()

    def _on_release(self, event: Any) -> None:
        if not self.active:
            return
        position = self._axes_position(event)
        active = self.active
        self.active = None
        if position is not None:
            self.on_moved(active, position[0], position[1])
