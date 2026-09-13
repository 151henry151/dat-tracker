"""Tests for cut mutate helpers used by the review TUI."""

from __future__ import annotations

from dat_tracker.review_edits import (
    delete_mid_cut,
    insert_mid_cut,
    nudge_cut,
    set_track_field,
)
from dat_tracker.review_plan import migrate_tracking_plan
from dat_tracker.tracking_plan import validate_tracking_plan


def _plan():
    return migrate_tracking_plan(
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


def test_nudge_mid_cut_preserves_endpoints():
    plan = nudge_cut(_plan(), cut_index=1, delta_sec=2.5)
    assert plan["cuts_sec"][0] == 0.0
    assert plan["cuts_sec"][-1] == 100.0
    assert plan["cuts_sec"][1] == 42.5
    assert len(plan["tracks"]) == 2
    assert plan["tracks"][0]["title"] == "A"
    validate_tracking_plan(plan)


def test_nudge_rejects_endpoint_cuts():
    plan = _plan()
    unchanged = nudge_cut(plan, cut_index=0, delta_sec=1.0)
    assert unchanged["cuts_sec"] == plan["cuts_sec"]


def test_insert_and_delete_mid_cut():
    plan = insert_mid_cut(_plan(), at_sec=70.0)
    assert 70.0 in plan["cuts_sec"]
    assert len(plan["tracks"]) == 3
    plan2 = delete_mid_cut(plan, cut_index=2)
    assert 70.0 not in plan2["cuts_sec"]
    assert len(plan2["tracks"]) == 2
    validate_tracking_plan(plan2)


def test_insert_split_keeps_title_on_best_overlap_only():
    """Inserting a cut inside a song must not clone the title onto both halves."""
    plan = insert_mid_cut(_plan(), at_sec=20.0)
    assert len(plan["tracks"]) == 3
    # Original A was 0-40; only the larger overlap half should keep "A".
    a_holders = [t for t in plan["tracks"] if t.get("title") == "A"]
    assert len(a_holders) == 1
    # The other fragment of A should be untitled (user fills or re-types).
    first_two = plan["tracks"][:2]
    assert sum(1 for t in first_two if t.get("title") is None) == 1
    # Trailing song B still titled.
    assert plan["tracks"][-1]["title"] == "B"
    validate_tracking_plan(plan)


def test_insert_does_not_shift_titles_by_index():
    """Regression: index-based reapply turned a banter slot into the next song's title."""
    plan = migrate_tracking_plan(
        {
            "schema_version": "1.0.0",
            "show_id": "x",
            "source_path": "x.flac",
            "duration_sec": 200.0,
            "cuts_sec": [0.0, 80.0, 100.0, 200.0],
            "tracks": [
                {
                    "index": 1,
                    "start_sec": 0.0,
                    "end_sec": 80.0,
                    "track_type": "song",
                    "title": "SongOne",
                    "segue_into_next": False,
                    "confidence": 0.8,
                    "evidence": [],
                },
                {
                    "index": 2,
                    "start_sec": 80.0,
                    "end_sec": 100.0,
                    "track_type": "banter",
                    "title": None,
                    "segue_into_next": False,
                    "confidence": 0.8,
                    "evidence": [],
                },
                {
                    "index": 3,
                    "start_sec": 100.0,
                    "end_sec": 200.0,
                    "track_type": "song",
                    "title": "SongTwo",
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
    # Split SongOne; banter and SongTwo must keep identity.
    out = insert_mid_cut(plan, at_sec=40.0)
    by_start = sorted(out["tracks"], key=lambda t: float(t["start_sec"]))
    assert by_start[-1]["title"] == "SongTwo"
    assert by_start[-1]["track_type"] == "song"
    banter = next(t for t in by_start if float(t["start_sec"]) == 80.0)
    assert banter["track_type"] == "banter"
    assert banter.get("title") in (None, "")


def test_set_track_title_and_type():
    plan = set_track_field(_plan(), track_index=1, title="Hello", track_type="banter")
    assert plan["tracks"][0]["title"] == "Hello"
    assert plan["tracks"][0]["track_type"] == "banter"
    validate_tracking_plan(plan)
