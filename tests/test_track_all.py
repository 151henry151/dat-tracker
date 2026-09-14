"""Tests for dump show-list Track all."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import patch

import pytest

from dat_tracker.review_discover import ReviewableShow


def _show(show_id: str, *, needs_tracking: bool) -> ReviewableShow:
    return ReviewableShow(
        show_id=show_id,
        plan_path=Path(f"/tmp/{show_id}/tracking_plan_gemini.json"),
        source_path=Path(f"/tmp/{show_id}.flac"),
        review_status="untracked" if needs_tracking else "pending",
        track_count=0 if needs_tracking else 3,
        duration_sec=None if needs_tracking else 10.0,
        work_dir=Path(f"/tmp/{show_id}"),
        needs_tracking=needs_tracking,
        relative_path=f"{show_id}.flac",
    )


def test_picker_track_all_dismisses_sentinel_when_untracked(tmp_path: Path):
    pytest.importorskip("textual")
    from dat_tracker.tui_review.picker import ShowPickerScreen
    from textual.app import App

    shows = [_show("a", needs_tracking=True), _show("b", needs_tracking=False)]

    class Host(App[object]):
        def on_mount(self) -> None:
            self.push_screen(
                ShowPickerScreen(shows, dump_root=tmp_path),
                self._done,
            )

        def _done(self, result: object) -> None:
            self.exit(result)

    app = Host()

    async def run() -> None:
        async with app.run_test() as pilot:
            await pilot.pause()
            assert "Track all" in str(app.screen.BINDINGS) or any(
                b.key == "a" for b in app.screen.BINDINGS
            )
            app.screen.action_track_all()
            await pilot.pause()
        assert app.return_value == "track_all"

    asyncio.run(run())


def test_picker_track_all_noop_without_untracked(tmp_path: Path):
    pytest.importorskip("textual")
    from dat_tracker.tui_review.picker import ShowPickerScreen
    from textual.app import App
    from textual.widgets import Static

    shows = [_show("a", needs_tracking=False)]

    class Host(App[object]):
        def on_mount(self) -> None:
            self.push_screen(
                ShowPickerScreen(shows, dump_root=tmp_path),
                lambda r: None,
            )

    app = Host()

    async def run() -> None:
        async with app.run_test() as pilot:
            await pilot.pause()
            app.screen.action_track_all()
            await pilot.pause()
            assert isinstance(app.screen, ShowPickerScreen)
            hint = str(app.screen.query_one("#hint", Static).content)
            assert "No untracked" in hint

    asyncio.run(run())


def test_track_all_screen_tracks_each_untracked(tmp_path: Path):
    pytest.importorskip("textual")
    from dat_tracker.tui_review.picker import ShowPickerScreen
    from dat_tracker.tui_review.session import (
        ConfirmTrackAllScreen,
        ReviewSessionApp,
        TrackAllScreen,
    )

    untracked = [
        _show("one", needs_tracking=True),
        _show("two", needs_tracking=True),
    ]
    pending = _show("done", needs_tracking=False)
    tracked: list[str] = []

    def fake_ensure(show, **_kwargs):  # noqa: ANN001
        tracked.append(show.show_id)
        return ReviewableShow(
            show_id=show.show_id,
            plan_path=show.plan_path,
            source_path=show.source_path,
            review_status="pending",
            track_count=2,
            duration_sec=10.0,
            work_dir=show.work_dir,
            needs_tracking=False,
            relative_path=show.relative_path,
        )

    app = ReviewSessionApp(
        shows=untracked + [pending],
        project_root=tmp_path,
        dump_first=False,
        dump_root=tmp_path,
    )

    async def run() -> None:
        async with app.run_test() as pilot:
            await pilot.pause()
            assert isinstance(app.screen, ShowPickerScreen)
            app.screen.action_track_all()
            for _ in range(40):
                if isinstance(app.screen, ConfirmTrackAllScreen):
                    break
                await pilot.pause(0.05)
            assert isinstance(app.screen, ConfirmTrackAllScreen)
            with patch(
                "dat_tracker.tui_review.session.ensure_show_tracked",
                fake_ensure,
            ):
                app.screen.action_confirm()
                for _ in range(80):
                    if isinstance(app.screen, ShowPickerScreen):
                        break
                    # May pass through TrackAllScreen
                    await pilot.pause(0.05)
            assert isinstance(app.screen, ShowPickerScreen)
            assert tracked == ["one", "two"]

    asyncio.run(run())
