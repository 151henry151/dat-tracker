"""Single Textual process: show picker → prepare → review (no terminal bounce)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from textual import work
from textual.app import App
from textual.screen import Screen
from textual.widgets import Footer, Header, Static

from dat_tracker.review_discover import ReviewableShow
from dat_tracker.tui_review.app import ReviewScreen
from dat_tracker.tui_review.picker import ShowPickerScreen


class PreparingScreen(Screen[tuple[Path, dict[str, Any], Path | None] | None]):
    """In-TUI wait while titles / package metadata are prepared."""

    CSS = """
    #prep {
        width: 1fr;
        height: 1fr;
        content-align: center middle;
        padding: 2 4;
    }
    """

    def __init__(
        self,
        show: ReviewableShow,
        *,
        project_root: Path,
        approved_by: str | None = None,
        artist: str | None = None,
        date: str | None = None,
        tracker: str | None = None,
        venue: str | None = None,
        city: str | None = None,
        state: str | None = None,
        source_override: Path | None = None,
    ) -> None:
        super().__init__()
        self.show = show
        self.project_root = Path(project_root)
        self.approved_by = approved_by
        self.artist = artist
        self.date = date
        self.tracker = tracker
        self.venue = venue
        self.city = city
        self.state = state
        self.source_override = source_override

    def compose(self):  # type: ignore[override]
        yield Header(show_clock=True)
        yield Static(
            f"Preparing review for {self.show.show_id}\n"
            "(titles, package metadata…)",
            id="prep",
        )
        yield Footer()

    def _prepare(
        self,
    ) -> tuple[Path, dict[str, Any], Path | None]:
        # Lazy import avoids a review_cli ↔ session cycle at module load.
        from dat_tracker.review_cli import _resolve_source, prepare_plan

        plan_path = self.show.plan_path
        raw = json.loads(plan_path.read_text())
        plan = prepare_plan(
            raw,
            project_root=self.project_root,
            artist=self.artist,
            date=self.date,
            tracker=self.tracker or self.approved_by,
            venue=self.venue,
            city=self.city,
            state=self.state,
        )
        source = _resolve_source(
            plan=plan,
            explicit=self.source_override,
            project_root=self.project_root,
            fallback=self.show.source_path,
        )
        return plan_path, plan, source

    def on_mount(self) -> None:
        self.prepare_show()

    @work(thread=True, exclusive=True)
    def prepare_show(self) -> None:
        try:
            result = self._prepare()
        except Exception as exc:  # noqa: BLE001 — surface in TUI
            self.app.call_from_thread(self._fail, str(exc))
            return
        self.app.call_from_thread(self.dismiss, result)

    def _fail(self, message: str) -> None:
        self.query_one("#prep", Static).update(
            f"Failed to prepare {self.show.show_id}:\n{message}\n\n"
            "Returning to show list…"
        )
        self.app.call_later(self.dismiss, None)


class ReviewSessionApp(App[int]):
    """Picker and review in one App.run() so the terminal never reappears mid-flow."""

    def __init__(
        self,
        *,
        shows: list[ReviewableShow],
        project_root: Path,
        approved_by: str | None = None,
        artist: str | None = None,
        date: str | None = None,
        tracker: str | None = None,
        venue: str | None = None,
        city: str | None = None,
        state: str | None = None,
        source_override: Path | None = None,
    ) -> None:
        super().__init__()
        self.shows = list(shows)
        self.project_root = Path(project_root)
        self.approved_by = approved_by
        self.artist = artist
        self.date = date
        self.tracker = tracker
        self.venue = venue
        self.city = city
        self.state = state
        self.source_override = source_override
        self.exit_code = 1

    def on_mount(self) -> None:
        self.push_screen(ShowPickerScreen(self.shows), self._on_picked)

    def _on_picked(self, show: ReviewableShow | None) -> None:
        if show is None:
            self.exit(1)
            return
        self.push_screen(
            PreparingScreen(
                show,
                project_root=self.project_root,
                approved_by=self.approved_by,
                artist=self.artist,
                date=self.date,
                tracker=self.tracker,
                venue=self.venue,
                city=self.city,
                state=self.state,
                source_override=self.source_override,
            ),
            self._on_prepared,
        )

    def _on_prepared(
        self, result: tuple[Path, dict[str, Any], Path | None] | None
    ) -> None:
        if result is None:
            # Preparation failed — return to picker rather than dumping to shell.
            self.push_screen(ShowPickerScreen(self.shows), self._on_picked)
            return
        plan_path, plan, source = result
        self.push_screen(
            ReviewScreen(
                plan_path=plan_path,
                plan=plan,
                source_audio=source,
                approved_by=self.approved_by,
                rehydrate=False,
            )
        )


def run_review_session(
    *,
    shows: list[ReviewableShow],
    project_root: Path,
    approved_by: str | None = None,
    artist: str | None = None,
    date: str | None = None,
    tracker: str | None = None,
    venue: str | None = None,
    city: str | None = None,
    state: str | None = None,
    source_override: Path | None = None,
) -> int:
    app = ReviewSessionApp(
        shows=shows,
        project_root=project_root,
        approved_by=approved_by,
        artist=artist,
        date=date,
        tracker=tracker,
        venue=venue,
        city=city,
        state=state,
        source_override=source_override,
    )
    result = app.run()
    if isinstance(result, int):
        return result
    return int(getattr(app, "exit_code", 1))
