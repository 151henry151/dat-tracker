"""Tests for LLM tracking-plan schema and heuristic dry-run drafts."""

from pathlib import Path

import pytest

from dat_tracker.tracking_plan import (
    TRACKING_PLAN_SCHEMA_PATH,
    build_draft_tracking_plan,
    validate_tracking_plan,
)


def test_tracking_plan_schema_file_exists():
    assert TRACKING_PLAN_SCHEMA_PATH.is_file()


def test_validate_accepts_minimal_valid_plan():
    plan = {
        "schema_version": "1.0.0",
        "show_id": "del2001-04-27.flac16",
        "source_path": "data/calibration/del2001-04-27.flac16/synthetic_continuous.flac",
        "duration_sec": 829.08,
        "cuts_sec": [0.0, 215.0, 375.0, 687.0, 829.08],
        "tracks": [
            {
                "index": 1,
                "start_sec": 0.0,
                "end_sec": 215.0,
                "track_type": "song",
                "title": None,
                "segue_into_next": False,
                "confidence": 0.6,
                "evidence": ["energy"],
            },
            {
                "index": 2,
                "start_sec": 215.0,
                "end_sec": 375.0,
                "track_type": "banter",
                "title": None,
                "segue_into_next": False,
                "confidence": 0.8,
                "evidence": ["speech_island"],
            },
            {
                "index": 3,
                "start_sec": 375.0,
                "end_sec": 687.0,
                "track_type": "song",
                "title": None,
                "segue_into_next": False,
                "confidence": 0.5,
                "evidence": ["energy_fill"],
            },
            {
                "index": 4,
                "start_sec": 687.0,
                "end_sec": 829.08,
                "track_type": "song",
                "title": None,
                "segue_into_next": False,
                "confidence": 0.5,
                "evidence": ["energy_fill"],
            },
        ],
        "overall_confidence": 0.6,
        "needs_review": False,
        "notes": [],
    }
    validate_tracking_plan(plan)


def test_validate_rejects_missing_tracks():
    plan = {
        "schema_version": "1.0.0",
        "show_id": "x",
        "source_path": "a.flac",
        "duration_sec": 10.0,
        "cuts_sec": [0.0, 10.0],
        "overall_confidence": 0.1,
        "needs_review": True,
        "notes": [],
    }
    with pytest.raises(Exception):
        validate_tracking_plan(plan)


def test_build_draft_tracking_plan_labels_speech_heavy_as_banter():
    cuts = [0.0, 212.0, 365.0, 659.0, 829.0]
    islands = [
        {"start": 215.0, "end": 224.0, "text": "banter one"},
        {"start": 370.0, "end": 396.0, "text": "encore ask"},
    ]
    plan = build_draft_tracking_plan(
        show_id="del2001-04-27.flac16",
        source_path="synth.flac",
        duration_sec=829.0,
        cuts_sec=cuts,
        speech_islands=islands,
        speech_cut_sec={215.0, 370.0},
        review_confidence_below=0.45,
    )
    validate_tracking_plan(plan)
    assert plan["show_id"] == "del2001-04-27.flac16"
    assert len(plan["tracks"]) == 4
    # Track starting near banter island onset should be banter-leaning or song with speech evidence.
    t2 = plan["tracks"][1]
    assert t2["start_sec"] == 212.0
    assert "speech_island" in t2["evidence"] or t2["track_type"] == "banter"
