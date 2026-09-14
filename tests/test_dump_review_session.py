"""Tests for dump-root → show list → optional track → review session."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from dat_tracker.catalog_io import write_catalog
from dat_tracker.review_discover import ReviewableShow
from dat_tracker.review_plan import migrate_tracking_plan


def _minimal_plan(*, show_id: str, source: str) -> dict:
    return migrate_tracking_plan(
        {
            "schema_version": "1.0.0",
            "show_id": show_id,
            "source_path": source,
            "duration_sec": 10.0,
            "cuts_sec": [0.0, 10.0],
            "tracks": [
                {
                    "index": 1,
                    "start_sec": 0.0,
                    "end_sec": 10.0,
                    "track_type": "song",
                    "title": "A",
                    "segue_into_next": False,
                    "confidence": 0.5,
                    "evidence": [],
                }
            ],
            "overall_confidence": 0.5,
            "needs_review": False,
            "notes": [],
        }
    )


def test_session_starts_at_dump_root_screen(tmp_path: Path):
    pytest.importorskip("textual")
    from dat_tracker.tui_review.dump_root import DumpRootScreen
    from dat_tracker.tui_review.session import ReviewSessionApp

    app = ReviewSessionApp(shows=[], project_root=tmp_path, dump_first=True)

    async def run() -> None:
        async with app.run_test() as pilot:
            await pilot.pause()
            assert isinstance(app.screen, DumpRootScreen)

    asyncio.run(run())


def test_session_tracks_untracked_then_opens_review(tmp_path: Path):
    pytest.importorskip("textual")
    from dat_tracker.tui_review.app import ReviewScreen
    from dat_tracker.tui_review.picker import ShowPickerScreen
    from dat_tracker.tui_review.session import (
        PreparingScreen,
        ReviewSessionApp,
        TrackingScreen,
    )

    dump = tmp_path / "dump"
    flac = dump / "show_a.flac"
    flac.parent.mkdir(parents=True)
    flac.write_bytes(b"f")
    write_catalog(
        tmp_path / "catalog",
        [
            {
                "id": "show_a",
                "raw_path": "show_a.flac",
                "artist": "Artist",
                "date": "2000-01-02",
                "status": "todo",
            }
        ],
    )
    plan_path = tmp_path / "data" / "work" / "show_a" / "tracking_plan_gemini.json"
    plan = _minimal_plan(show_id="show_a", source=str(flac))

    def fake_track(show, **_kwargs):  # noqa: ANN001
        plan_path.parent.mkdir(parents=True, exist_ok=True)
        plan_path.write_text(json.dumps(plan) + "\n")
        return ReviewableShow(
            show_id="show_a",
            plan_path=plan_path,
            source_path=flac,
            review_status="pending",
            track_count=1,
            duration_sec=10.0,
            work_dir=plan_path.parent,
            needs_tracking=False,
            relative_path="show_a.flac",
            artist="Artist",
            date="2000-01-02",
        )

    def fake_prepare(self):  # noqa: ANN001
        return plan_path, plan, flac

    app = ReviewSessionApp(
        shows=[],
        project_root=tmp_path,
        dump_first=True,
        initial_dump_root=dump,
    )

    async def run() -> None:
        async with app.run_test() as pilot:
            await pilot.pause()
            # Directory browser — confirm the initial dump folder.
            from dat_tracker.tui_review.dump_root import DumpRootScreen

            assert isinstance(app.screen, DumpRootScreen)
            app.screen.action_confirm()
            for _ in range(40):
                if isinstance(app.screen, ShowPickerScreen):
                    break
                await pilot.pause(0.05)
            assert isinstance(app.screen, ShowPickerScreen)
            with (
                patch.object(ReviewSessionApp, "_remember_dump_root"),
                patch(
                    "dat_tracker.tui_review.session.ensure_show_tracked",
                    fake_track,
                ),
                patch.object(PreparingScreen, "_prepare", fake_prepare),
            ):
                await pilot.press("enter")
                for _ in range(80):
                    if isinstance(app.screen, ReviewScreen):
                        break
                    await pilot.pause(0.05)
            assert isinstance(app.screen, ReviewScreen)
            assert app.screen.plan.get("show_id") == "show_a"

    asyncio.run(run())


def test_ensure_show_tracked_invokes_run_track_show(tmp_path: Path):
    from dat_tracker.tui_review.session import ensure_show_tracked

    flac = tmp_path / "a.flac"
    flac.write_bytes(b"f")
    show = ReviewableShow(
        show_id="a",
        plan_path=tmp_path / "data" / "work" / "a" / "tracking_plan_gemini.json",
        source_path=flac,
        review_status="untracked",
        track_count=0,
        duration_sec=None,
        work_dir=tmp_path / "data" / "work" / "a",
        needs_tracking=True,
        relative_path="a.flac",
        artist="Band",
        date="1999-01-01",
    )
    plan = _minimal_plan(show_id="a", source=str(flac))

    def fake_run_track_show(**kwargs):
        assert kwargs["show_id"] == "a"
        assert kwargs["source_audio"] == flac
        assert kwargs["artist"] == "Band"
        assert kwargs["date"] == "1999-01-01"
        assert kwargs["skip_package"] is True
        assert kwargs["interactive_review"] is False
        path = kwargs["work_root"] / "a" / "tracking_plan_gemini.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(plan) + "\n")
        return {"plan": plan, "paths": {"plan": str(path)}}

    with patch("dat_tracker.track_show.run_track_show", fake_run_track_show):
        out = ensure_show_tracked(show, project_root=tmp_path)
    assert out.needs_tracking is False
    assert out.plan_path.is_file()
    assert out.review_status == "pending"
