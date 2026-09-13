"""Unit tests for TUI helper formatting (no terminal required)."""

from dat_tracker.tui_review.widgets.package_form import package_form_values
from dat_tracker.tui_review.widgets.track_table import format_track_rows
from dat_tracker.review_plan import migrate_tracking_plan


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
