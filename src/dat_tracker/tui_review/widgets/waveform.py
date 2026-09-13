"""Waveform overview / detail widgets for the review TUI."""

from __future__ import annotations

from typing import Any

from rich.text import Text
from textual.reactive import reactive
from textual.widget import Widget

from dat_tracker.waveform import (
    render_envelope_panel,
    render_time_ruler,
    slice_envelope_window,
)


class WaveformView(Widget):
    """Renders a multi-row peak silhouette with cut markers and playhead."""

    DEFAULT_CSS = """
    WaveformView {
        height: 8;
        border: solid $accent;
        padding: 0 1;
    }
    """

    peaks: reactive[list[float]] = reactive(list)
    duration_sec: reactive[float] = reactive(1.0)
    markers_sec: reactive[list[float]] = reactive(list)
    playhead_sec: reactive[float | None] = reactive(None)
    selected_marker_sec: reactive[float | None] = reactive(None)
    viewport_sec: reactive[tuple[float, float] | None] = reactive(None)
    label: reactive[str] = reactive("")
    panel_height: reactive[int] = reactive(5)

    def __init__(
        self,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        panel_height: int = 5,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes)
        self.panel_height = panel_height

    def set_envelope(
        self,
        env: dict[str, Any],
        *,
        window: tuple[float, float] | None = None,
    ) -> None:
        if window is None:
            self.peaks = [float(p) for p in env["peaks"]]
            self.duration_sec = float(env["duration_sec"])
        else:
            start, end = window
            sliced = slice_envelope_window(env, start_sec=start, end_sec=end)
            self.peaks = [float(p) for p in sliced]
            self.duration_sec = max(0.01, end - start)
        self.refresh()

    def render(self) -> Text:
        width = max(8, self.size.width - 2)
        height = max(2, min(self.panel_height, max(2, self.size.height - 3)))
        title = self.label or "waveform"
        if not self.peaks:
            return Text.from_markup(f"[dim]{title}[/dim]\n(no envelope)")
        panel = render_envelope_panel(
            self.peaks,
            width=width,
            height=height,
            markers_sec=self.markers_sec,
            duration_sec=self.duration_sec,
            playhead_sec=self.playhead_sec,
            selected_marker_sec=self.selected_marker_sec,
            viewport_sec=self.viewport_sec,
        )
        ruler = render_time_ruler(duration_sec=self.duration_sec, width=width)
        out = Text()
        out.append(title + "\n", style="bold")
        for i, line in enumerate(panel.splitlines()):
            styled = Text()
            for ch in line:
                if ch in ("|", "║"):
                    styled.append(ch, style="bold yellow")
                elif ch == "▶":
                    styled.append(ch, style="bold cyan")
                elif ch == "·":
                    styled.append(ch, style="dim cyan")
                elif ch == "█":
                    styled.append(ch, style="bright_white")
                else:
                    styled.append(ch)
            out.append(styled)
            out.append("\n")
        out.append(ruler, style="dim")
        return out


class DetailWaveformView(WaveformView):
    """Detail view stores absolute window start for marker remapping."""

    window_start_sec: reactive[float] = reactive(0.0)
    absolute_markers: reactive[list[float]] = reactive(list)
    absolute_playhead: reactive[float | None] = reactive(None)

    DEFAULT_CSS = """
    DetailWaveformView {
        height: 10;
        border: solid $secondary;
        padding: 0 1;
    }
    """

    def __init__(
        self,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        panel_height: int = 6,
    ) -> None:
        super().__init__(
            name=name, id=id, classes=classes, panel_height=panel_height
        )

    def set_detail(
        self,
        env: dict[str, Any],
        *,
        center_sec: float,
        half_window_sec: float = 20.0,
        markers_sec: list[float] | None = None,
        playhead_sec: float | None = None,
        selected_marker_sec: float | None = None,
    ) -> tuple[float, float]:
        duration = float(env["duration_sec"])
        start = max(0.0, center_sec - half_window_sec)
        end = min(duration, center_sec + half_window_sec)
        if end - start < 1.0:
            end = min(duration, start + 1.0)
        self.window_start_sec = start
        self.absolute_markers = list(markers_sec or [])
        self.absolute_playhead = playhead_sec
        self.label = f"detail: {start:.1f}s–{end:.1f}s"
        self.viewport_sec = None
        self.set_envelope(env, window=(start, end))
        local = [m - start for m in self.absolute_markers if start <= m <= end]
        self.markers_sec = local
        if selected_marker_sec is not None and start <= selected_marker_sec <= end:
            self.selected_marker_sec = selected_marker_sec - start
        else:
            self.selected_marker_sec = None
        if playhead_sec is not None and start <= playhead_sec <= end:
            self.playhead_sec = playhead_sec - start
        else:
            self.playhead_sec = None
        self.refresh()
        return (start, end)
