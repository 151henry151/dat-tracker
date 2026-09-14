"""Show-picker TUI: choose a tracked show to review."""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import DataTable, Footer, Header, Static

from dat_tracker.review_discover import ReviewableShow


class ShowPickerApp(App[ReviewableShow | None]):
    """List reviewable shows; Enter opens the selected show."""

    CSS = """
    #hint {
        height: 3;
        padding: 0 1;
        color: $text-muted;
    }
    #shows {
        height: 1fr;
    }
    """

    BINDINGS = [
        Binding("q", "quit_picker", "Quit", show=True),
        Binding("enter", "open_selected", "Open", show=True),
        Binding("r", "refresh", "Refresh", show=True),
    ]

    def __init__(self, shows: list[ReviewableShow]) -> None:
        super().__init__()
        self.shows = list(shows)
        self._by_row: dict[int, ReviewableShow] = {}

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static(
            "Select a show and press Enter to review. "
            "q quits. Shows come from data/work/*/tracking_plan*.json.",
            id="hint",
        )
        yield DataTable(id="shows")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#shows", DataTable)
        table.cursor_type = "row"
        table.add_columns("Show", "Status", "Tracks", "Audio", "Duration")
        self._fill_table()
        if not self.shows:
            self.query_one("#hint", Static).update(
                "No reviewable shows found under data/work. "
                "Run tracking first, or pass --plan PATH."
            )

    def _fill_table(self) -> None:
        table = self.query_one("#shows", DataTable)
        table.clear()
        self._by_row.clear()
        for i, show in enumerate(self.shows):
            dur = (
                f"{show.duration_sec / 60.0:.1f}m"
                if show.duration_sec is not None
                else "—"
            )
            table.add_row(
                show.show_id,
                show.review_status,
                str(show.track_count),
                "yes" if show.has_audio else "missing",
                dur,
            )
            self._by_row[i] = show

    def _selected(self) -> ReviewableShow | None:
        table = self.query_one("#shows", DataTable)
        if table.cursor_row is None:
            return None
        return self._by_row.get(int(table.cursor_row))

    def action_open_selected(self) -> None:
        show = self._selected()
        if show is None:
            return
        self.query_one("#hint", Static).update(
            f"Opening {show.show_id} — preparing review…"
        )
        # Let the hint paint before we tear down the picker.
        self.set_timer(0.05, lambda: self.exit(show))

    def action_quit_picker(self) -> None:
        self.exit(None)

    def action_refresh(self) -> None:
        # Caller replaces shows before remount if needed; here just redraw.
        self._fill_table()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.cursor_row is None:
            return
        show = self._by_row.get(int(event.cursor_row))
        if show is not None:
            self.query_one("#hint", Static).update(
                f"Opening {show.show_id} — preparing review…"
            )
            self.set_timer(0.05, lambda: self.exit(show))


def run_show_picker(shows: list[ReviewableShow]) -> ReviewableShow | None:
    app = ShowPickerApp(shows)
    result = app.run()
    if isinstance(result, ReviewableShow):
        return result
    return None
