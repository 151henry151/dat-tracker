"""Single Textual process: dump root → show picker → track? → prepare → review."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from textual import work
from textual.app import App
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Footer, Header, ProgressBar, Static

from dat_tracker.dump_discover import default_dump_root, discover_dump_shows
from dat_tracker.review_discover import ReviewableShow, discover_reviewable_shows
from dat_tracker.tui_review.app import ReviewScreen
from dat_tracker.tui_review.dump_root import DumpRootScreen
from dat_tracker.tui_review.picker import TRACK_ALL, ShowPickerScreen


def ensure_show_tracked(
    show: ReviewableShow,
    *,
    project_root: Path,
    work_dir: Path | None = None,
    tracker: str | None = None,
    on_progress: Any | None = None,
) -> ReviewableShow:
    """Run the LLM tracker when the dump FLAC has no plan yet; return an updated show."""
    if not show.needs_tracking and show.plan_path.is_file():
        return show
    if show.source_path is None or not show.source_path.is_file():
        raise FileNotFoundError(f"Missing source audio for {show.show_id}")

    from dat_tracker.track_show import run_track_show

    root = Path(project_root)
    work_root = Path(work_dir) if work_dir is not None else root / "data" / "work"
    artist = (show.artist or "").strip() or "Unknown Artist"
    date = (show.date or "").strip() or "1970-01-01"
    result = run_track_show(
        source_audio=show.source_path,
        show_id=show.show_id,
        work_root=work_root,
        artist=artist,
        date=date,
        tracker=tracker or "dat-tracker",
        venue=None,
        city=None,
        state=None,
        project_root=root,
        skip_package=True,
        interactive_review=False,
        accept_all_review=False,
        force_unreviewed=False,
        on_progress=on_progress,
    )
    plan_path = work_root / show.show_id / "tracking_plan_gemini.json"
    paths_map = result.get("paths") if isinstance(result.get("paths"), dict) else {}
    if paths_map.get("plan"):
        plan_path = Path(str(paths_map["plan"]))
    if not plan_path.is_file():
        plan = result.get("plan")
        if isinstance(plan, dict):
            plan_path.parent.mkdir(parents=True, exist_ok=True)
            plan_path.write_text(json.dumps(plan, indent=2) + "\n")
        else:
            raise RuntimeError(f"Tracking did not write a plan for {show.show_id}")
    doc = json.loads(plan_path.read_text())
    review = doc.get("review") if isinstance(doc.get("review"), dict) else {}
    tracks = doc.get("tracks") if isinstance(doc.get("tracks"), list) else []
    duration = doc.get("duration_sec")
    return ReviewableShow(
        show_id=str(doc.get("show_id") or show.show_id),
        plan_path=plan_path,
        source_path=show.source_path,
        review_status=str(review.get("status") or "pending"),
        track_count=len(tracks),
        duration_sec=float(duration) if duration is not None else None,
        work_dir=plan_path.parent,
        needs_tracking=False,
        relative_path=show.relative_path,
        artist=show.artist,
        date=show.date,
    )


class PreparingScreen(Screen[tuple[Path, dict[str, Any], Path | None] | None]):
    """In-TUI wait while titles / package metadata are prepared."""

    CSS = """
    #prep-wrap {
        width: 1fr;
        height: auto;
        padding: 2 4;
    }
    #prep-title { text-style: bold; height: 1; }
    #prep-stage { padding-top: 1; height: auto; }
    #prep-bar {
        width: 100%;
        height: 1;
        margin: 1 0;
    }
    #prep-pct { height: 1; }
    #prep-elapsed { height: 1; color: $accent; }
    #prep-note { color: $text-muted; height: auto; padding-top: 1; }
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
        self._started = 0.0
        self._elapsed_timer = None

    def compose(self):  # type: ignore[override]
        from textual.containers import Vertical

        yield Header(show_clock=True)
        with Vertical(id="prep-wrap"):
            yield Static(f"Preparing review for {self.show.show_id}", id="prep-title")
            yield Static("Starting…", id="prep-stage")
            yield ProgressBar(total=100, show_eta=False, id="prep-bar")
            yield Static("0%", id="prep-pct")
            yield Static("Elapsed: 0s", id="prep-elapsed")
            yield Static(
                "Companion Gemini extract and package polish can take a minute.",
                id="prep-note",
            )
        yield Footer()

    def on_mount(self) -> None:
        import time

        self._started = time.monotonic()
        self._elapsed_timer = self.set_interval(1.0, self._tick_elapsed)
        self.prepare_show()

    def _tick_elapsed(self) -> None:
        import time

        elapsed = max(0, int(time.monotonic() - self._started))
        mins, secs = divmod(elapsed, 60)
        self.query_one("#prep-elapsed", Static).update(
            f"Elapsed: {mins}m {secs:02d}s (still running)"
        )

    def _on_progress(self, message: str, fraction: float) -> None:
        pct = int(round(fraction * 100))
        self.query_one("#prep-stage", Static).update(message)
        self.query_one("#prep-bar", ProgressBar).update(progress=pct)
        self.query_one("#prep-pct", Static).update(f"{pct}%")

    def _prepare(
        self,
        on_progress: Any | None = None,
    ) -> tuple[Path, dict[str, Any], Path | None]:
        # Lazy import avoids a review_cli ↔ session cycle at module load.
        from dat_tracker.review_cli import _resolve_source, prepare_plan

        plan_path = self.show.plan_path
        raw = json.loads(plan_path.read_text())
        plan = prepare_plan(
            raw,
            project_root=self.project_root,
            artist=self.artist or self.show.artist,
            date=self.date or self.show.date,
            tracker=self.tracker or self.approved_by,
            venue=self.venue,
            city=self.city,
            state=self.state,
            on_progress=on_progress,
        )
        source = _resolve_source(
            plan=plan,
            explicit=self.source_override,
            project_root=self.project_root,
            fallback=self.show.source_path,
        )
        return plan_path, plan, source

    @work(thread=True, exclusive=True)
    def prepare_show(self) -> None:
        def on_progress(message: str, fraction: float) -> None:
            self.app.call_from_thread(self._on_progress, message, fraction)

        try:
            result = self._prepare(on_progress=on_progress)
        except Exception as exc:  # noqa: BLE001 — surface in TUI
            self.app.call_from_thread(self._fail, str(exc))
            return
        self.app.call_from_thread(self._done, result)

    def _done(self, result: tuple[Path, dict[str, Any], Path | None]) -> None:
        if self._elapsed_timer is not None:
            self._elapsed_timer.stop()
        self.dismiss(result)

    def _fail(self, message: str) -> None:
        if self._elapsed_timer is not None:
            self._elapsed_timer.stop()
        self.query_one("#prep-stage", Static).update(
            f"Failed to prepare {self.show.show_id}:\n{message}\n\n"
            "Returning to show list…"
        )
        self.app.call_later(self.dismiss, None)

    def on_unmount(self) -> None:
        if self._elapsed_timer is not None:
            self._elapsed_timer.stop()


class TrackingScreen(Screen[ReviewableShow | None]):
    """In-TUI wait while Gemini tracking writes a plan for an untracked FLAC."""

    CSS = """
    #track-wrap {
        width: 1fr;
        height: auto;
        max-height: 100%;
        padding: 2 4;
    }
    #track-title { text-style: bold; height: 1; }
    #track-path { color: $text-muted; height: auto; }
    #track-stage { padding-top: 1; height: auto; }
    #track-note { color: $text-muted; height: auto; padding-top: 1; }
    #show-bar {
        width: 100%;
        height: 1;
        margin: 1 0;
    }
    #show-pct { height: 1; }
    #track-elapsed { height: 1; color: $accent; }
    """

    def __init__(
        self,
        show: ReviewableShow,
        *,
        project_root: Path,
        work_dir: Path | None = None,
        tracker: str | None = None,
    ) -> None:
        super().__init__()
        self.show = show
        self.project_root = Path(project_root)
        self.work_dir = work_dir
        self.tracker = tracker
        self._started = 0.0
        self._elapsed_timer = None

    def compose(self):  # type: ignore[override]
        from textual.containers import Vertical

        yield Header(show_clock=True)
        with Vertical(id="track-wrap"):
            yield Static(f"Tracking {self.show.show_id}", id="track-title")
            yield Static(
                str(self.show.relative_path or self.show.source_path or ""),
                id="track-path",
            )
            yield Static("Starting…", id="track-stage")
            yield Static(
                "Long stages (Whisper, ffmpeg silence, Gemini API) keep updating "
                "elapsed time so the UI does not look hung.",
                id="track-note",
            )
            yield ProgressBar(total=100, show_eta=False, id="show-bar")
            yield Static("Current show: 0%", id="show-pct")
            yield Static("Elapsed: 0s", id="track-elapsed")
        yield Footer()

    def on_mount(self) -> None:
        import time

        self._started = time.monotonic()
        self._elapsed_timer = self.set_interval(1.0, self._tick_elapsed)
        self.run_tracking()

    def _tick_elapsed(self) -> None:
        import time

        elapsed = max(0, int(time.monotonic() - self._started))
        mins, secs = divmod(elapsed, 60)
        self.query_one("#track-elapsed", Static).update(
            f"Elapsed: {mins}m {secs:02d}s (still running)"
        )

    def _on_progress(self, message: str, fraction: float) -> None:
        pct = int(round(fraction * 100))
        self.query_one("#track-stage", Static).update(message)
        self.query_one("#show-bar", ProgressBar).update(progress=pct)
        self.query_one("#show-pct", Static).update(f"Current show: {pct}%")

    @work(thread=True, exclusive=True)
    def run_tracking(self) -> None:
        def on_progress(message: str, fraction: float) -> None:
            self.app.call_from_thread(self._on_progress, message, fraction)

        try:
            result = ensure_show_tracked(
                self.show,
                project_root=self.project_root,
                work_dir=self.work_dir,
                tracker=self.tracker,
                on_progress=on_progress,
            )
        except Exception as exc:  # noqa: BLE001
            self.app.call_from_thread(self._fail, str(exc))
            return
        self.app.call_from_thread(self._done, result)

    def _done(self, result: ReviewableShow) -> None:
        if self._elapsed_timer is not None:
            self._elapsed_timer.stop()
        self.dismiss(result)

    def _fail(self, message: str) -> None:
        if self._elapsed_timer is not None:
            self._elapsed_timer.stop()
        self.query_one("#track-stage", Static).update(
            f"Tracking failed for {self.show.show_id}:\n{message}\n\n"
            "Returning to show list…"
        )
        self.app.call_later(self.dismiss, None)

    def on_unmount(self) -> None:
        if self._elapsed_timer is not None:
            self._elapsed_timer.stop()


class ConfirmTrackAllScreen(Screen[bool]):
    """Confirm batch-tracking every untracked show in the dump list."""

    CSS = """
    #confirm-body {
        width: 1fr;
        height: 1fr;
        content-align: center middle;
        padding: 2 4;
    }
    #confirm-actions {
        height: 3;
        padding: 0 2;
    }
    """

    BINDINGS = [
        Binding("enter", "confirm", "Track all", show=True),
        Binding("y", "confirm", "Track all", show=False),
        Binding("n", "cancel", "Cancel", show=True),
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("q", "cancel", "Cancel", show=False),
    ]

    def __init__(self, *, count: int) -> None:
        super().__init__()
        self.count = count

    def compose(self):  # type: ignore[override]
        from textual.containers import Vertical
        from textual.widgets import Button

        yield Header(show_clock=True)
        yield Static(
            f"Track all {self.count} untracked show(s)?\n\n"
            "Each show runs Whisper + Gemini and may take several minutes.\n"
            "A long list can take hours and will use Gemini API quota.\n"
            "When finished you return to the show list to open any show for "
            "waveform review.\n"
            "Failed shows are skipped; the list refreshes when finished.",
            id="confirm-body",
        )
        with Vertical(id="confirm-actions"):
            yield Button("Track all", id="track-all-yes", variant="primary")
            yield Button("Cancel", id="track-all-no")
        yield Footer()

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)

    def on_button_pressed(self, event) -> None:  # noqa: ANN001
        from textual.widgets import Button

        if not isinstance(event.button, Button):
            return
        if event.button.id == "track-all-yes":
            self.action_confirm()
        elif event.button.id == "track-all-no":
            self.action_cancel()


class TrackAllScreen(Screen[dict[str, Any]]):
    """Track every untracked show sequentially with live overall + per-show progress."""

    CSS = """
    #track-all-wrap {
        width: 1fr;
        height: auto;
        padding: 2 4;
    }
    #batch-summary { text-style: bold; height: auto; }
    #overall-bar, #show-bar {
        width: 100%;
        height: 1;
        margin: 1 0;
    }
    #track-path { color: $text-muted; height: auto; }
    #track-stage { padding-top: 1; height: auto; }
    #track-errors { color: $warning; padding-top: 1; height: auto; }
    #track-note { color: $text-muted; height: auto; }
    #track-elapsed { height: 1; color: $accent; }
    """

    def __init__(
        self,
        shows: list[ReviewableShow],
        *,
        project_root: Path,
        work_dir: Path | None = None,
        tracker: str | None = None,
    ) -> None:
        super().__init__()
        self.shows = list(shows)
        self.project_root = Path(project_root)
        self.work_dir = work_dir
        self.tracker = tracker
        self._index = 0
        self._show_frac = 0.0
        self._failed = 0
        self._started = 0.0
        self._elapsed_timer = None

    def compose(self):  # type: ignore[override]
        from textual.containers import Vertical

        total = len(self.shows)
        yield Header(show_clock=True)
        with Vertical(id="track-all-wrap"):
            yield Static(
                f"Track all — 0 / {total} shows (0%)",
                id="batch-summary",
            )
            yield ProgressBar(total=100, show_eta=False, id="overall-bar")
            yield Static("Current show: —", id="current-show")
            yield Static("", id="track-path")
            yield Static("Starting…", id="track-stage")
            yield ProgressBar(total=100, show_eta=False, id="show-bar")
            yield Static("Current show: 0%", id="show-pct")
            yield Static("Elapsed: 0s", id="track-elapsed")
            yield Static(
                "Whisper on large DAT FLACs is often many minutes on CPU.",
                id="track-note",
            )
            yield Static("", id="track-errors")
        yield Footer()

    def on_mount(self) -> None:
        import time

        self._started = time.monotonic()
        self._elapsed_timer = self.set_interval(1.0, self._tick_elapsed)
        self.run_batch()

    def _tick_elapsed(self) -> None:
        import time

        elapsed = max(0, int(time.monotonic() - self._started))
        mins, secs = divmod(elapsed, 60)
        self.query_one("#track-elapsed", Static).update(
            f"Elapsed: {mins}m {secs:02d}s (still running)"
        )

    def _overall_pct(self) -> float:
        total = max(len(self.shows), 1)
        return 100.0 * (self._index - 1 + self._show_frac) / total

    def _refresh_ui(
        self,
        *,
        show_id: str,
        path: str,
        stage: str,
        show_frac: float,
        failed: int,
    ) -> None:
        total = len(self.shows)
        self._show_frac = show_frac
        overall = self._overall_pct()
        done = max(self._index - 1, 0)
        self.query_one("#batch-summary", Static).update(
            f"Track all — {done} / {total} complete · overall {overall:.0f}%"
        )
        self.query_one("#overall-bar", ProgressBar).update(progress=overall)
        self.query_one("#current-show", Static).update(
            f"Now tracking {self._index}/{total}: {show_id}"
        )
        self.query_one("#track-path", Static).update(path)
        self.query_one("#track-stage", Static).update(stage)
        show_pct = int(round(show_frac * 100))
        self.query_one("#show-bar", ProgressBar).update(progress=show_pct)
        self.query_one("#show-pct", Static).update(f"Current show: {show_pct}%")
        if failed:
            self.query_one("#track-errors", Static).update(
                f"{failed} failed so far (continuing)…"
            )

    @work(thread=True, exclusive=True)
    def run_batch(self) -> None:
        ok = 0
        failed: list[str] = []
        total = len(self.shows)
        for i, show in enumerate(self.shows, start=1):
            self._index = i
            self._show_frac = 0.0
            path = str(show.relative_path or show.source_path or "")

            def on_progress(
                message: str,
                fraction: float,
                *,
                _show_id: str = show.show_id,
                _path: str = path,
            ) -> None:
                self.app.call_from_thread(
                    self._refresh_ui,
                    show_id=_show_id,
                    path=_path,
                    stage=message,
                    show_frac=fraction,
                    failed=len(failed),
                )

            self.app.call_from_thread(
                self._refresh_ui,
                show_id=show.show_id,
                path=path,
                stage="Starting…",
                show_frac=0.0,
                failed=len(failed),
            )
            try:
                ensure_show_tracked(
                    show,
                    project_root=self.project_root,
                    work_dir=self.work_dir,
                    tracker=self.tracker,
                    on_progress=on_progress,
                )
                ok += 1
            except Exception as exc:  # noqa: BLE001
                failed.append(f"{show.show_id}: {exc}")
                self.app.call_from_thread(
                    self._refresh_ui,
                    show_id=show.show_id,
                    path=path,
                    stage=f"Failed: {exc}",
                    show_frac=1.0,
                    failed=len(failed),
                )
        summary = {"ok": ok, "failed": failed, "total": total}
        self.app.call_from_thread(self._finish, summary)

    def _finish(self, summary: dict[str, Any]) -> None:
        if self._elapsed_timer is not None:
            self._elapsed_timer.stop()
        self.dismiss(summary)

    def on_unmount(self) -> None:
        if self._elapsed_timer is not None:
            self._elapsed_timer.stop()


class ReviewSessionApp(App[int]):
    """Dump root (optional) → picker → track? → prepare → review in one App.run()."""

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
        dump_first: bool = False,
        initial_dump_root: Path | None = None,
        work_dir: Path | None = None,
        dump_root: Path | None = None,
        prompt_defaults: bool = False,
        prompt_gemini_key: bool = False,
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
        self.dump_first = dump_first
        self.initial_dump_root = initial_dump_root
        self.work_dir = work_dir
        self.dump_root = dump_root
        self.prompt_defaults = prompt_defaults
        self.prompt_gemini_key = prompt_gemini_key
        self.exit_code = 1

    def on_mount(self) -> None:
        self._continue_first_run_prompts()

    def _continue_first_run_prompts(self) -> None:
        if self.prompt_defaults:
            from dat_tracker.review_defaults import defaults_are_configured
            from dat_tracker.tui_review.defaults_setup import DefaultsSetupScreen

            if not defaults_are_configured(project_root=self.project_root):
                self.prompt_defaults = False
                self.push_screen(
                    DefaultsSetupScreen(project_root=self.project_root),
                    self._on_defaults_done,
                )
                return
            self.prompt_defaults = False
        if self.prompt_gemini_key:
            from dat_tracker.gemini_tracker import gemini_api_key_is_configured
            from dat_tracker.tui_review.gemini_key_setup import GeminiApiKeyScreen

            if not gemini_api_key_is_configured(project_root=self.project_root):
                self.prompt_gemini_key = False
                self.push_screen(
                    GeminiApiKeyScreen(project_root=self.project_root),
                    self._on_gemini_key_done,
                )
                return
            self.prompt_gemini_key = False
        self._open_entry_screen()

    def _on_defaults_done(self, _saved: bool | None) -> None:
        self._continue_first_run_prompts()

    def _on_gemini_key_done(self, _saved: bool | None) -> None:
        self._continue_first_run_prompts()

    def _open_entry_screen(self) -> None:
        if self.dump_first:
            initial = self.initial_dump_root or default_dump_root(self.project_root)
            self.push_screen(
                DumpRootScreen(
                    project_root=self.project_root,
                    initial_path=initial,
                ),
                self._on_dump_root,
            )
        else:
            self.push_screen(
                ShowPickerScreen(self.shows, dump_root=self.dump_root),
                self._on_picked,
            )

    def _on_dump_root(self, path: Path | str | None) -> None:
        if path is None:
            self.exit(1)
            return
        if path == "work_plans":
            work = self.work_dir or (self.project_root / "data" / "work")
            self.dump_root = None
            self.shows = discover_reviewable_shows(
                project_root=self.project_root, work_dir=work
            )
        else:
            dump = Path(path)
            self.dump_root = dump
            self.shows = discover_dump_shows(
                dump,
                project_root=self.project_root,
                work_dir=self.work_dir,
            )
            self._remember_dump_root(dump)
        self.push_screen(
            ShowPickerScreen(self.shows, dump_root=self.dump_root),
            self._on_picked,
        )

    def _remember_dump_root(self, path: Path) -> None:
        try:
            from dat_tracker.review_defaults import user_defaults_path

            target = user_defaults_path()
            target.parent.mkdir(parents=True, exist_ok=True)
            existing: dict[str, Any] = {}
            if target.is_file():
                try:
                    raw = json.loads(target.read_text())
                    if isinstance(raw, dict):
                        existing = raw
                except (OSError, json.JSONDecodeError):
                    existing = {}
            existing["last_dump_root"] = str(path)
            target.write_text(json.dumps(existing, indent=2) + "\n")
        except OSError:
            pass

    def _on_picked(self, show: ReviewableShow | str | None) -> None:
        if show is None:
            if self.dump_first:
                initial = self.dump_root or self.initial_dump_root or default_dump_root(
                    self.project_root
                )
                self.push_screen(
                    DumpRootScreen(
                        project_root=self.project_root,
                        initial_path=initial,
                    ),
                    self._on_dump_root,
                )
                return
            self.exit(1)
            return
        if show == TRACK_ALL:
            untracked = [s for s in self.shows if s.needs_tracking]
            if not untracked:
                self._refresh_picker()
                return
            self.push_screen(
                ConfirmTrackAllScreen(count=len(untracked)),
                self._on_track_all_confirmed,
            )
            return
        assert isinstance(show, ReviewableShow)
        if show.needs_tracking or not show.plan_path.is_file():
            self.push_screen(
                TrackingScreen(
                    show,
                    project_root=self.project_root,
                    work_dir=self.work_dir,
                    tracker=self.tracker or self.approved_by,
                ),
                self._on_tracked,
            )
            return
        self._push_prepare(show)

    def _on_track_all_confirmed(self, confirmed: bool | None) -> None:
        if not confirmed:
            self._refresh_picker()
            return
        untracked = [s for s in self.shows if s.needs_tracking]
        self.push_screen(
            TrackAllScreen(
                untracked,
                project_root=self.project_root,
                work_dir=self.work_dir,
                tracker=self.tracker or self.approved_by,
            ),
            self._on_track_all_done,
        )

    def _on_track_all_done(self, summary: dict[str, Any] | None) -> None:
        self._refresh_picker()

    def _on_tracked(self, show: ReviewableShow | None) -> None:
        if show is None:
            self._refresh_picker()
            return
        # Refresh list entry for this show.
        self.shows = [
            show if s.show_id == show.show_id else s for s in self.shows
        ]
        self._push_prepare(show)

    def _push_prepare(self, show: ReviewableShow) -> None:
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

    def _refresh_picker(self) -> None:
        if self.dump_root is not None:
            self.shows = discover_dump_shows(
                self.dump_root,
                project_root=self.project_root,
                work_dir=self.work_dir,
            )
        self.push_screen(
            ShowPickerScreen(self.shows, dump_root=self.dump_root),
            self._on_picked,
        )

    def _on_prepared(
        self, result: tuple[Path, dict[str, Any], Path | None] | None
    ) -> None:
        if result is None:
            self._refresh_picker()
            return
        plan_path, plan, source = result
        self.push_screen(
            ReviewScreen(
                plan_path=plan_path,
                plan=plan,
                source_audio=source,
                approved_by=self.approved_by,
                rehydrate=False,
                project_root=self.project_root,
            ),
            self._on_reviewed,
        )

    def _on_reviewed(self, result: Any) -> None:
        if not (isinstance(result, tuple) and result and result[0] == "approved"):
            # Quit without approve — stay in the TUI and return to the show list.
            self._refresh_picker()
            return
        approved = result[1]
        from dat_tracker.review_cli import _resolve_source
        from dat_tracker.tui_review.post_approve import run_post_approve_flow

        source = _resolve_source(
            plan=approved,
            explicit=self.source_override,
            project_root=self.project_root,
            fallback=None,
        )

        def on_another() -> None:
            self._refresh_picker()

        def on_back() -> None:
            self.push_screen(
                ReviewScreen(
                    plan_path=self._plan_path_for(approved),
                    plan=approved,
                    source_audio=source,
                    approved_by=self.approved_by,
                    rehydrate=False,
                    project_root=self.project_root,
                ),
                self._on_reviewed,
            )

        run_post_approve_flow(
            self,
            plan=approved,
            plan_path=self._plan_path_for(approved),
            source_audio=source,
            project_root=self.project_root,
            allow_another=True,
            on_another=on_another,
            on_back_to_review=on_back,
        )

    def _plan_path_for(self, plan: dict[str, Any]) -> Path:
        show_id = str(plan.get("show_id") or "")
        for show in self.shows:
            if show.show_id == show_id:
                return show.plan_path
        return self.project_root / "data" / "work" / show_id / "tracking_plan_gemini.json"


def run_review_session(
    *,
    shows: list[ReviewableShow] | None = None,
    project_root: Path,
    approved_by: str | None = None,
    artist: str | None = None,
    date: str | None = None,
    tracker: str | None = None,
    venue: str | None = None,
    city: str | None = None,
    state: str | None = None,
    source_override: Path | None = None,
    dump_first: bool = False,
    initial_dump_root: Path | None = None,
    work_dir: Path | None = None,
    dump_root: Path | None = None,
    prompt_defaults: bool = False,
    prompt_gemini_key: bool = False,
) -> int:
    app = ReviewSessionApp(
        shows=list(shows or []),
        project_root=project_root,
        approved_by=approved_by,
        artist=artist,
        date=date,
        tracker=tracker,
        venue=venue,
        city=city,
        state=state,
        source_override=source_override,
        dump_first=dump_first,
        initial_dump_root=initial_dump_root,
        work_dir=work_dir,
        dump_root=dump_root,
        prompt_defaults=prompt_defaults,
        prompt_gemini_key=prompt_gemini_key,
    )
    result = app.run()
    if isinstance(result, int):
        return result
    return int(getattr(app, "exit_code", 1))
