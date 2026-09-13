"""Tests for LLM as-delivered plan snapshots and review reset."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dat_tracker.review_baseline import (
    as_delivered_path,
    ensure_as_delivered_snapshot,
    load_as_delivered,
    reset_plan_to_as_delivered,
    write_as_delivered_snapshot,
)
from dat_tracker.review_plan import migrate_tracking_plan


def _plan(*, cuts: list[float], title: str = "Song") -> dict:
    tracks = []
    for i in range(len(cuts) - 1):
        tracks.append(
            {
                "index": i + 1,
                "start_sec": cuts[i],
                "end_sec": cuts[i + 1],
                "track_type": "song",
                "title": title if i == 0 else f"T{i+1}",
                "segue_into_next": False,
                "confidence": 0.8,
                "evidence": [],
            }
        )
    return migrate_tracking_plan(
        {
            "schema_version": "1.0.0",
            "show_id": "x",
            "source_path": "x.flac",
            "duration_sec": cuts[-1],
            "cuts_sec": cuts,
            "tracks": tracks,
            "overall_confidence": 0.8,
            "needs_review": False,
            "notes": ["llm note"],
        }
    )


def test_write_as_delivered_snapshot_once(tmp_path: Path):
    plan_path = tmp_path / "tracking_plan_gemini.json"
    delivered = _plan(cuts=[0.0, 40.0, 100.0])
    plan_path.write_text(json.dumps(delivered) + "\n")
    snap = write_as_delivered_snapshot(plan_path, delivered, overwrite=True)
    assert snap == as_delivered_path(plan_path)
    assert snap.is_file()

    edited = _plan(cuts=[0.0, 20.0, 40.0, 100.0], title="Edited")
    write_as_delivered_snapshot(plan_path, edited, overwrite=False)
    loaded = load_as_delivered(plan_path)
    assert loaded is not None
    assert loaded["cuts_sec"] == [0.0, 40.0, 100.0]
    assert loaded["tracks"][0]["title"] == "Song"


def test_ensure_as_delivered_creates_missing(tmp_path: Path):
    plan_path = tmp_path / "tracking_plan_gemini.json"
    plan = _plan(cuts=[0.0, 50.0, 100.0])
    plan_path.write_text(json.dumps(plan) + "\n")
    assert not as_delivered_path(plan_path).is_file()
    ensure_as_delivered_snapshot(plan_path, plan)
    assert load_as_delivered(plan_path)["cuts_sec"] == [0.0, 50.0, 100.0]


def test_reset_restores_cuts_keeps_package():
    delivered = _plan(cuts=[0.0, 40.0, 100.0])
    current = _plan(cuts=[0.0, 20.0, 40.0, 100.0], title="Edited")
    current["package"]["artist"] = "Keep Artist"
    current["package"]["tracker"] = "Henry"
    out = reset_plan_to_as_delivered(current, delivered, keep_package=True)
    assert out["cuts_sec"] == [0.0, 40.0, 100.0]
    assert len(out["tracks"]) == 2
    assert out["tracks"][0]["title"] == "Song"
    assert out["package"]["artist"] == "Keep Artist"
    assert out["package"]["tracker"] == "Henry"
    assert out["review"]["status"] == "pending"


def test_reset_without_snapshot_raises(tmp_path: Path):
    plan_path = tmp_path / "tracking_plan_gemini.json"
    from dat_tracker.review_baseline import require_as_delivered

    with pytest.raises(FileNotFoundError):
        require_as_delivered(plan_path)
