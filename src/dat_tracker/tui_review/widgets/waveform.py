"""Waveform overview / detail widgets for the review TUI."""

from __future__ import annotations

from typing import Any

from rich.text import Text
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget

from dat_tracker.waveform import (
    nearest_cut_index_at_column,
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
    WaveformView:focus {
        border: double $accent;
    }
    """

    can_focus = True

    peaks: reactive[list[float]] = reactive(list)
    duration_sec: reactive[float] = reactive(1.0)
    markers_sec: reactive[list[float]] = reactive(list)
    playhead_sec: reactive[float | None] = reactive(None)
    selected_marker_sec: reactive[float | None] = reactive(None)
    viewport_sec: reactive[tuple[float, float] | None] = reactive(None)
    label: reactive[str] = reactive("")
    panel_height: reactive[int] = reactive(5)
    # Absolute cut times (for overview hit-testing / messaging).
    absolute_markers: reactive[list[float]] = reactive(list)
    time_offset_sec: reactive[float] = reactive(0.0)

    class CutMarkerClicked(Message):
        """Posted when the user clicks near a cut marker."""

        def __init__(self, cut_index: int, time_sec: float) -> None:
            super().__init__()
            self.cut_index = cut_index
            self.time_sec = time_sec

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
        self._panel_width = 8
        self._panel_top_row = 1  # title occupies row 0 of the render

    def set_envelope(
        self,
        env: dict[str, Any],
        *,
        window: tuple[float, float] | None = None,
    ) -> None:
        if window is None:
            self.peaks = [float(p) for p in env["peaks"]]
            self.duration_sec = float(env["duration_sec"])
            self.time_offset_sec = 0.0
        else:
            start, end = window
            sliced = slice_envelope_window(env, start_sec=start, end_sec=end)
            self.peaks = [float(p) for p in sliced]
            self.duration_sec = max(0.01, end - start)
            self.time_offset_sec = start
        self.refresh()

    def render(self) -> Text:
        width = max(8, self.size.width - 2)
        self._panel_width = width
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
        for line in panel.splitlines():
            styled = Text()
            for ch in line:
                if ch == "║":
                    styled.append(ch, style="bold reverse yellow")
                elif ch == "|":
                    styled.append(ch, style="bold yellow")
                elif ch == "▶":
                    styled.append(ch, style="bold cyan")
                elif ch == "·":
                    styled.append(ch, style="dim cyan")
                elif ch in ("▄", "█"):
                    styled.append(ch, style="bright_white")
                else:
                    styled.append(ch)
            out.append(styled)
            out.append("\n")
        out.append(ruler, style="dim")
        return out

    def on_click(self, event) -> None:  # textual.events.Click
        """Select the nearest cut marker under the click (or nearby)."""
        self.focus()
        # event.x/y are relative to the widget; padding is 1 on left.
        col = int(event.x) - 1
        if col < 0:
            col = 0
        if col >= self._panel_width:
            col = self._panel_width - 1
        abs_markers = list(self.absolute_markers) or [
            float(t) + float(self.time_offset_sec) for t in self.markers_sec
        ]
        if not abs_markers:
            return
        local_cuts = [float(t) - float(self.time_offset_sec) for t in abs_markers]
        idx = nearest_cut_index_at_column(
            local_cuts,
            click_col=col,
            width=self._panel_width,
            duration_sec=self.duration_sec,
            max_col_distance=3,
        )
        if idx is None:
            from dat_tracker.waveform import column_to_time_sec

            t_local = column_to_time_sec(
                col, duration_sec=self.duration_sec, width=self._panel_width
            )
            abs_t = t_local + float(self.time_offset_sec)
            idx = min(
                range(len(abs_markers)),
                key=lambda i: abs(float(abs_markers[i]) - abs_t),
            )
        event.stop()
        self.post_message(self.CutMarkerClicked(idx, float(abs_markers[idx])))


class DetailWaveformView(WaveformView):
    """Detail view stores absolute window start for marker remapping."""

    window_start_sec: reactive[float] = reactive(0.0)
    absolute_playhead: reactive[float | None] = reactive(None)

    DEFAULT_CSS = """
    DetailWaveformView {
        height: 10;
        border: solid $secondary;
        padding: 0 1;
    }
    DetailWaveformView:focus {
        border: double $secondary;
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
        self.label = f"detail: {start:.1f}s–{end:.1f}s  (click cut, ←/→ nudge)"
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
