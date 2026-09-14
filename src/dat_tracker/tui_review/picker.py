"""Show-picker TUI: choose a tracked (or untracked dump) show to review."""

from __future__ import annotations

from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Static

from dat_tracker.review_discover import ReviewableShow

# Sentinel dismissed when the operator chooses Track all on a dump list.
TRACK_ALL = "track_all"


class ShowPickerScreen(Screen[ReviewableShow | str | None]):
    """List reviewable shows; Enter opens one, a tracks all untracked (dump lists)."""

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
        Binding("q", "quit_picker", "Back", show=True),
        Binding("enter", "open_selected", "Open", show=True),
        Binding("r", "refresh", "Refresh", show=True),
        Binding("a", "track_all", "Track all", show=True),
    ]

    def __init__(
        self,
        shows: list[ReviewableShow],
        *,
        dump_root: Path | None = None,
    ) -> None:
        super().__init__()
        self.shows = list(shows)
        self.dump_root = dump_root
        self._by_row: dict[int, ReviewableShow] = {}

    def untracked_shows(self) -> list[ReviewableShow]:
        return [s for s in self.shows if s.needs_tracking]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        if self.dump_root is not None:
            n = len(self.untracked_shows())
            extra = f" a tracks all ({n} untracked)." if n else ""
            hint = (
                f"Shows under {self.dump_root}. "
                f"Enter opens (tracks untracked FLACs first).{extra} q goes back."
            )
        else:
            hint = (
                "Select a show and press Enter to review. "
                "q quits. Shows come from data/work/*/tracking_plan*.json."
            )
        yield Static(hint, id="hint")
        yield DataTable(id="shows")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#shows", DataTable)
        table.cursor_type = "row"
        if self.dump_root is not None:
            table.add_columns("Show", "Status", "Tracks", "Audio", "Path")
        else:
            table.add_columns("Show", "Status", "Tracks", "Audio", "Duration")
        self._fill_table()
        if not self.shows:
            if self.dump_root is not None:
                self.query_one("#hint", Static).update(
                    f"No FLACs found under {self.dump_root}. q goes back."
                )
            else:
                self.query_one("#hint", Static).update(
                    "No reviewable shows found under data/work. "
                    "Run tracking first, or pass --plan PATH."
                )

    def _fill_table(self) -> None:
        table = self.query_one("#shows", DataTable)
        table.clear()
        self._by_row.clear()
        for i, show in enumerate(self.shows):
            if self.dump_root is not None:
                path_col = show.relative_path or (
                    str(show.source_path) if show.source_path else "—"
                )
                table.add_row(
                    show.show_id,
                    show.review_status,
                    str(show.track_count) if show.track_count else "—",
                    "yes" if show.has_audio else "missing",
                    path_col,
                )
            else:
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

    def _open_show(self, show: ReviewableShow) -> None:
        verb = "Tracking" if show.needs_tracking else "Opening"
        self.query_one("#hint", Static).update(f"{verb} {show.show_id}…")
        self.app.call_later(self.dismiss, show)

    def action_open_selected(self) -> None:
        show = self._selected()
        if show is None:
            return
        self._open_show(show)

    def action_track_all(self) -> None:
        if self.dump_root is None:
            return
        untracked = self.untracked_shows()
        if not untracked:
            self.query_one("#hint", Static).update(
                "No untracked shows in this list."
            )
            return
        self.dismiss(TRACK_ALL)

    def action_quit_picker(self) -> None:
        self.dismiss(None)

    def action_refresh(self) -> None:
        self._fill_table()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.cursor_row is None:
            return
        show = self._by_row.get(int(event.cursor_row))
        if show is not None:
            self._open_show(show)


class ShowPickerApp(App[ReviewableShow | None]):
    """Standalone picker (legacy / tests); prefer :class:`ReviewSessionApp`."""

    def __init__(self, shows: list[ReviewableShow]) -> None:
        super().__init__()
        self.shows = list(shows)

    def on_mount(self) -> None:
        self.push_screen(ShowPickerScreen(self.shows), self._done)

    def _done(self, show: ReviewableShow | None) -> None:
        self.exit(show)


def run_show_picker(shows: list[ReviewableShow]) -> ReviewableShow | None:
    app = ShowPickerApp(shows)
    result = app.run()
    if isinstance(result, ReviewableShow):
        return result
    return None
