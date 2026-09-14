"""Pilot test: approve dismisses into packaging screen (mocked build_package)."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from dat_tracker.package_pipeline import PackageResult
from dat_tracker.review_plan import migrate_tracking_plan


def test_approve_opens_packaging_screen(tmp_path: Path):
    pytest.importorskip("textual")
    from dat_tracker.tui_review.app import ReviewApp, ReviewScreen
    from dat_tracker.tui_review.post_approve import PackagingScreen

    show_id = "demo2001-01-01"
    plan_path = tmp_path / "tracking_plan_gemini.json"
    plan = migrate_tracking_plan(
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
            "package": {
                "artist": "Demo",
                "date": "2001-01-01",
                "venue": None,
                "city": None,
                "state": None,
                "source": None,
                "transfer": None,
                "transferer": None,
                "tracker": "Tester",
                "set_label": "One Set",
                "collection_subjects": [],
                "notes": None,
            },
        }
    )
    plan_path.write_text(json.dumps(plan) + "\n")
    source = tmp_path / "x.flac"
    source.write_bytes(b"fLaC")

    fake_result = PackageResult(
        show_id=show_id,
        out_dir=tmp_path / "data" / "out" / show_id,
        work_dir=tmp_path / "data" / "work" / show_id / "package",
        track_paths=[],
        track_count=1,
    )
    fake_result.out_dir.mkdir(parents=True)
    (fake_result.out_dir / f"{show_id}_t01.flac").write_bytes(b"fLaC")

    def fake_build(*_a, **_k):
        return fake_result

    app = ReviewApp(
        plan_path=plan_path,
        plan=plan,
        source_audio=source,
        approved_by="Tester",
        rehydrate=False,
        project_root=tmp_path,
    )

    async def run() -> None:
        async with app.run_test() as pilot:
            await pilot.pause()
            assert isinstance(app.screen, ReviewScreen)
            with patch(
                "dat_tracker.tui_review.post_approve.build_package",
                fake_build,
            ):
                await pilot.press("a")
                from dat_tracker.tui_review.post_approve import UploadConfirmScreen

                for _ in range(80):
                    if isinstance(app.screen, (PackagingScreen, UploadConfirmScreen)):
                        break
                    await pilot.pause(0.05)
                assert isinstance(
                    app.screen, (PackagingScreen, UploadConfirmScreen)
                ), f"unexpected screen {type(app.screen)}"

    asyncio.run(run())
