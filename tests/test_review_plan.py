"""Tests for tracking-plan review status, Accept-all, and package gate."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dat_tracker.review_plan import (
    ReviewNotApprovedError,
    approve_plan,
    assert_review_approved_for_package,
    is_review_approved,
    migrate_tracking_plan,
    review_status,
)
from dat_tracker.tracking_plan import validate_tracking_plan


def _minimal_v10_plan() -> dict:
    return {
        "schema_version": "1.0.0",
        "show_id": "demo-show",
        "source_path": "demo.flac",
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


def test_migrate_tracking_plan_adds_pending_review_and_package():
    migrated = migrate_tracking_plan(_minimal_v10_plan())
    assert migrated["schema_version"] == "1.1.0"
    assert migrated["review"]["status"] == "pending"
    assert "package" in migrated
    assert isinstance(migrated["package"], dict)
    validate_tracking_plan(migrated)
    # Cuts unchanged.
    assert migrated["cuts_sec"] == [0.0, 40.0, 100.0]


def test_approve_plan_accept_all_preserves_cuts():
    plan = migrate_tracking_plan(_minimal_v10_plan())
    cuts_before = list(plan["cuts_sec"])
    approved = approve_plan(plan, method="accept_all", approved_by="tester")
    assert approved["review"]["status"] == "approved"
    assert approved["review"]["method"] == "accept_all"
    assert approved["review"]["approved_by"] == "tester"
    assert approved["review"]["approved_at"]
    assert approved["cuts_sec"] == cuts_before
    assert is_review_approved(approved)
    validate_tracking_plan(approved)


def test_approve_plan_edited_sets_method():
    plan = migrate_tracking_plan(_minimal_v10_plan())
    approved = approve_plan(plan, method="edited")
    assert approved["review"]["method"] == "edited"
    assert is_review_approved(approved)


def test_assert_review_approved_refuses_pending():
    plan = migrate_tracking_plan(_minimal_v10_plan())
    assert review_status(plan) == "pending"
    with pytest.raises(ReviewNotApprovedError):
        assert_review_approved_for_package(plan)


def test_assert_review_approved_allows_force():
    plan = migrate_tracking_plan(_minimal_v10_plan())
    assert_review_approved_for_package(plan, force_unreviewed=True)


def test_assert_review_approved_allows_approved():
    plan = approve_plan(migrate_tracking_plan(_minimal_v10_plan()), method="accept_all")
    assert_review_approved_for_package(plan)


def test_accept_all_cli_writes_approved_plan(tmp_path: Path, monkeypatch):
    from dat_tracker.review_plan import accept_all_plan_file

    plan_path = tmp_path / "tracking_plan_gemini.json"
    plan_path.write_text(json.dumps(_minimal_v10_plan(), indent=2) + "\n")
    out = accept_all_plan_file(plan_path, approved_by="cli")
    assert out["review"]["status"] == "approved"
    assert out["review"]["method"] == "accept_all"
    reloaded = json.loads(plan_path.read_text())
    assert reloaded["review"]["status"] == "approved"
    validate_tracking_plan(reloaded)
