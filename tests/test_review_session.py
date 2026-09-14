"""Tests for picker → prepare → review session (single Textual process)."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from dat_tracker.review_discover import ReviewableShow
from dat_tracker.review_plan import migrate_tracking_plan


def test_review_session_opens_review_without_leaving_app(tmp_path: Path):
    pytest.importorskip("textual")
    from dat_tracker.tui_review.app import ReviewScreen
    from dat_tracker.tui_review.picker import ShowPickerScreen
    from dat_tracker.tui_review.session import PreparingScreen, ReviewSessionApp

    plan_path = tmp_path / "tracking_plan_gemini.json"
    plan = migrate_tracking_plan(
        {
            "schema_version": "1.0.0",
            "show_id": "demo-show",
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

    prepared = migrate_tracking_plan(plan)

    def fake_prepare(self):  # noqa: ANN001
        return plan_path, prepared, None

    app = ReviewSessionApp(shows=[show], project_root=tmp_path)

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
            assert app.screen.plan.get("show_id") == "demo-show"

    asyncio.run(run())
