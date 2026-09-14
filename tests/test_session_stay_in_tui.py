"""Tests: stay in one TUI for defaults + quit-back-to-picker."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from dat_tracker.review_discover import ReviewableShow
from dat_tracker.review_plan import migrate_tracking_plan


def _plan(show_id: str = "demo") -> dict:
    return migrate_tracking_plan(
        {
            "schema_version": "1.0.0",
            "show_id": show_id,
            "source_path": "x.flac",
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


def test_session_opens_defaults_when_unconfigured(tmp_path: Path, monkeypatch):
    pytest.importorskip("textual")
    monkeypatch.setenv("DAT_TRACKER_DEFAULTS", str(tmp_path / "defaults.json"))
    from dat_tracker.tui_review.defaults_setup import DefaultsSetupScreen
    from dat_tracker.tui_review.dump_root import DumpRootScreen
    from dat_tracker.tui_review.session import ReviewSessionApp

    app = ReviewSessionApp(
        shows=[],
        project_root=tmp_path,
        dump_first=True,
        prompt_defaults=True,
    )

    async def run() -> None:
        async with app.run_test() as pilot:
            await pilot.pause()
            assert isinstance(app.screen, DefaultsSetupScreen)
            app.screen.action_skip()
            for _ in range(40):
                if isinstance(app.screen, DumpRootScreen):
                    break
                await pilot.pause(0.05)
            assert isinstance(app.screen, DumpRootScreen)

    asyncio.run(run())


def test_session_quit_review_returns_to_picker(tmp_path: Path):
    pytest.importorskip("textual")
    from dat_tracker.tui_review.app import ReviewScreen
    from dat_tracker.tui_review.picker import ShowPickerScreen
    from dat_tracker.tui_review.session import PreparingScreen, ReviewSessionApp

    plan_path = tmp_path / "tracking_plan_gemini.json"
    plan = _plan("demo-show")
    plan_path.write_text(json.dumps(plan) + "\n")
    show = ReviewableShow(
        show_id="demo-show",
        plan_path=plan_path,
        source_path=None,
        review_status="pending",
        track_count=1,
        duration_sec=10.0,
        work_dir=tmp_path,
    )

    def fake_prepare(self):  # noqa: ANN001
        return plan_path, plan, None

    app = ReviewSessionApp(shows=[show], project_root=tmp_path, dump_first=False)

    async def run() -> None:
        async with app.run_test() as pilot:
            await pilot.pause()
            assert isinstance(app.screen, ShowPickerScreen)
            with patch.object(PreparingScreen, "_prepare", fake_prepare):
                await pilot.press("enter")
                for _ in range(50):
                    if isinstance(app.screen, ReviewScreen):
                        break
                    await pilot.pause(0.05)
            assert isinstance(app.screen, ReviewScreen)
            await pilot.press("q")
            for _ in range(50):
                if isinstance(app.screen, ShowPickerScreen):
                    break
                await pilot.pause(0.05)
            assert isinstance(app.screen, ShowPickerScreen)
            assert app.is_running

    asyncio.run(run())
