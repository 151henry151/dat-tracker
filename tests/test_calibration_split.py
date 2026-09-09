"""Tests for Tier B train/holdout split helpers."""

from pathlib import Path

import pytest

from dat_tracker.calibration_split import (
    load_tier_b_manifest,
    show_ids_for_split,
    summarize_split_scores,
)


def test_load_tier_b_manifest_lists_train_and_holdout(tmp_path: Path):
    manifest = tmp_path / "calibration_tier_b.json"
    manifest.write_text(
        """
{
  "schema_version": "1.0.0",
  "tier": "B",
  "shows": [
    {"id": "a", "split": "holdout", "artist": "A", "date": "2001-01-01"},
    {"id": "b", "split": "train", "artist": "B", "date": "2001-01-02"},
    {"id": "c", "split": "train", "artist": "C", "date": "2001-01-03"}
  ]
}
""".strip()
        + "\n"
    )
    rows = load_tier_b_manifest(manifest)
    assert [r["id"] for r in rows] == ["a", "b", "c"]
    assert show_ids_for_split(rows, "train") == ["b", "c"]
    assert show_ids_for_split(rows, "holdout") == ["a"]


def test_summarize_split_scores_reports_mean_min_and_track_gate():
    rows = [
        {"id": "x", "f1": 1.0, "track_count_delta": 0},
        {"id": "y", "f1": 0.8, "track_count_delta": 1},
        {"id": "z", "f1": 0.6, "track_count_delta": 3},
    ]
    summary = summarize_split_scores(rows, track_delta_ok=1)
    assert summary["mean_f1"] == pytest.approx(0.8)
    assert summary["min_f1"] == 0.6
    assert summary["track_count_ok_fraction"] == pytest.approx(2 / 3)
    assert summary["n"] == 3
