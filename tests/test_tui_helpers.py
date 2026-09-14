"""Unit tests for TUI helper formatting and package field wiring."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from dat_tracker.review_plan import migrate_tracking_plan
from dat_tracker.tui_review.widgets.package_form import (
    PACKAGE_FIELD_ORDER,
    package_field_tooltip,
    package_form_values,
)
from dat_tracker.tui_review.widgets.track_table import format_track_rows
from dat_tracker.tui_review.widgets.waveform import waveform_glyph_style


def test_silence_baseline_matches_braille_glyph_color():
    assert waveform_glyph_style("·") == waveform_glyph_style("⣿")
    assert waveform_glyph_style("·") == "bright_white"
    assert waveform_glyph_style("▶") == "bold reverse cyan"
    assert waveform_glyph_style("┃") == "bold reverse cyan"


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


def test_resolve_track_row_selection_cut_and_playhead():
    from dat_tracker.tui_review.widgets.track_table import resolve_track_row_selection

    tracks = [
        {"index": 1, "start_sec": 0.0, "end_sec": 40.0},
        {"index": 2, "start_sec": 40.0, "end_sec": 100.0},
    ]
    cuts = [0.0, 40.0, 100.0]
    assert resolve_track_row_selection(tracks, cuts, 1) == (1, 40.0)
    assert resolve_track_row_selection(tracks, cuts, 0) == (0, 0.0)
    assert resolve_track_row_selection(tracks, cuts, 99) is None
    assert resolve_track_row_selection(tracks, [], 0) is None


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


def test_package_field_tooltips_cover_all_fields_and_mention_ia():
    for key in PACKAGE_FIELD_ORDER:
        tip = package_field_tooltip(key)
        assert tip
        assert len(tip) > 20
    assert "creator" in package_field_tooltip("artist")
    assert "coverage" in package_field_tooltip("city")
    assert "lineage" in package_field_tooltip("transfer")
    assert "transferer" in package_field_tooltip("transferer")


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

    from dat_tracker.tui_review.app import ReviewApp, ReviewScreen

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

    app = ReviewApp(
        plan_path=Path("plan.json"), plan=plan, source_audio=None, rehydrate=False
    )

    async def run() -> None:
        async with app.run_test() as pilot:
            await pilot.pause()
            review = app.screen
            assert isinstance(review, ReviewScreen)
            artist = review.query_one("#pkg-artist", Input)
            date = review.query_one("#pkg-date", Input)
            venue = review.query_one("#pkg-venue", Input)
            assert artist.value == "Sam Bush"
            assert date.value == "2001-04-27"
            assert venue.value == "Merlefest"
            assert artist.compact is True
            assert artist.tooltip and "creator" in str(artist.tooltip)
            artist.focus()
            await pilot.pause()
            # Jump to end of "Sam Bush" then append.
            for _ in range(20):
                await pilot.press("right")
            await pilot.press("space", "Z")
            assert "Z" in review.query_one("#pkg-artist", Input).value

    asyncio.run(run())


def test_review_app_select_cut_and_nudge_with_arrows():
    pytest.importorskip("textual")
    from dat_tracker.tui_review.app import ReviewApp, ReviewScreen

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
    app = ReviewApp(
        plan_path=Path("plan.json"), plan=plan, source_audio=None, rehydrate=False
    )

    async def run() -> None:
        async with app.run_test() as pilot:
            await pilot.pause()
            review = app.screen
            assert isinstance(review, ReviewScreen)
            review._select_cut(1, status_prefix="Selected cut")
            await pilot.pause()
            assert review.selected_cut_index == 1
            # Same default as clicking a yellow cut: loop-window start (~8s before).
            assert review._playhead == pytest.approx(32.0)
            before = float(review.plan["cuts_sec"][1])
            review.query_one("#overview").focus()
            await pilot.pause()
            await pilot.press("right")
            await pilot.pause()
            after = float(review.plan["cuts_sec"][1])
            assert after == pytest.approx(before + 0.1)
            await pilot.press("]")
            await pilot.pause()
            assert review.selected_cut_index == 2
            assert review._playhead == pytest.approx(92.0)  # 100 - 8

    asyncio.run(run())
