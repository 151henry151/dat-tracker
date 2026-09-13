"""Unit tests for TUI helper formatting and package field wiring."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from dat_tracker.review_plan import migrate_tracking_plan
from dat_tracker.tui_review.widgets.package_form import package_form_values
from dat_tracker.tui_review.widgets.track_table import format_track_rows


def test_format_track_rows():
    plan = migrate_tracking_plan(
        {
            "schema_version": "1.0.0",
            "show_id": "x",
            "source_path": "x.flac",
            "duration_sec": 100.0,
            "cuts_sec": [0.0, 40.0, 100.0],
            "tracks": [
                {
                    "index": 1,
                    "start_sec": 0.0,
                    "end_sec": 40.0,
                    "track_type": "song",
                    "title": "A",
                    "segue_into_next": True,
                    "confidence": 0.8,
                    "evidence": [],
                },
                {
                    "index": 2,
                    "start_sec": 40.0,
                    "end_sec": 100.0,
                    "track_type": "banter",
                    "title": None,
                    "segue_into_next": False,
                    "confidence": 0.8,
                    "evidence": [],
                },
            ],
            "overall_confidence": 0.8,
            "needs_review": False,
            "notes": [],
        }
    )
    rows = format_track_rows(plan)
    assert rows[0][0] == "1"
    assert rows[0][2] == "A"
    assert rows[0][3] == ">"
    assert rows[1][1] == "banter"


def test_package_form_values_defaults():
    plan = migrate_tracking_plan(
        {
            "schema_version": "1.0.0",
            "show_id": "x",
            "source_path": "x.flac",
            "duration_sec": 10.0,
            "cuts_sec": [0.0, 10.0],
            "tracks": [
                {
                    "index": 1,
                    "start_sec": 0.0,
                    "end_sec": 10.0,
                    "track_type": "song",
                    "title": None,
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
    vals = package_form_values(plan)
    assert vals["artist"] == ""
    plan["package"]["artist"] = "Demo"
    assert package_form_values(plan)["artist"] == "Demo"


def test_package_form_values_preserves_seeded_fields():
    plan = migrate_tracking_plan(
        {
            "schema_version": "1.0.0",
            "show_id": "sbb2001-04-27.flac16",
            "source_path": "x.flac",
            "duration_sec": 10.0,
            "cuts_sec": [0.0, 10.0],
            "tracks": [
                {
                    "index": 1,
                    "start_sec": 0.0,
                    "end_sec": 10.0,
                    "track_type": "song",
                    "title": None,
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
    plan["package"]["date"] = "2001-04-27"
    plan["package"]["venue"] = "Merlefest"
    plan["package"]["city"] = "Wilkesboro"
    vals = package_form_values(plan)
    assert vals["date"] == "2001-04-27"
    assert vals["venue"] == "Merlefest"
    assert vals["city"] == "Wilkesboro"


def test_review_app_package_inputs_receive_seeded_values():
    """Compact package Inputs must show seeded text and accept edits."""
    pytest.importorskip("textual")
    from textual.widgets import Input

    from dat_tracker.tui_review.app import ReviewApp

    plan = migrate_tracking_plan(
        {
            "schema_version": "1.0.0",
            "show_id": "sbb2001-04-27.flac16",
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
    plan["package"]["artist"] = "Sam Bush"
    plan["package"]["date"] = "2001-04-27"
    plan["package"]["venue"] = "Merlefest"

    app = ReviewApp(plan_path=Path("plan.json"), plan=plan, source_audio=None)

    async def run() -> None:
        async with app.run_test() as pilot:
            await pilot.pause()
            artist = app.query_one("#pkg-artist", Input)
            date = app.query_one("#pkg-date", Input)
            venue = app.query_one("#pkg-venue", Input)
            assert artist.value == "Sam Bush"
            assert date.value == "2001-04-27"
            assert venue.value == "Merlefest"
            assert artist.compact is True
            artist.focus()
            await pilot.pause()
            # Jump to end of "Sam Bush" then append.
            for _ in range(20):
                await pilot.press("right")
            await pilot.press("space", "Z")
            assert "Z" in app.query_one("#pkg-artist", Input).value

    asyncio.run(run())


def test_review_app_select_cut_and_nudge_with_arrows():
    pytest.importorskip("textual")
    from dat_tracker.tui_review.app import ReviewApp

    plan = migrate_tracking_plan(
        {
            "schema_version": "1.0.0",
            "show_id": "demo",
            "source_path": "x.flac",
            "duration_sec": 100.0,
            "cuts_sec": [0.0, 40.0, 100.0],
            "tracks": [
                {
                    "index": 1,
                    "start_sec": 0.0,
                    "end_sec": 40.0,
                    "track_type": "song",
                    "title": "A",
                    "segue_into_next": False,
                    "confidence": 0.8,
                    "evidence": [],
                },
                {
                    "index": 2,
                    "start_sec": 40.0,
                    "end_sec": 100.0,
                    "track_type": "song",
                    "title": "B",
                    "segue_into_next": False,
                    "confidence": 0.8,
                    "evidence": [],
                },
            ],
            "overall_confidence": 0.8,
            "needs_review": False,
            "notes": [],
        }
    )
    app = ReviewApp(plan_path=Path("plan.json"), plan=plan, source_audio=None)

    async def run() -> None:
        async with app.run_test() as pilot:
            await pilot.pause()
            app._select_cut(1, status_prefix="Selected cut")
            await pilot.pause()
            assert app.selected_cut_index == 1
            before = float(app.plan["cuts_sec"][1])
            app.query_one("#overview").focus()
            await pilot.pause()
            await pilot.press("right")
            await pilot.pause()
            after = float(app.plan["cuts_sec"][1])
            assert after == pytest.approx(before + 0.1)

    asyncio.run(run())
