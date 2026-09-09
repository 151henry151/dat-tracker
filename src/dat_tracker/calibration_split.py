"""Tier B calibration manifest: train vs holdout splits."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_tier_b_manifest(path: Path) -> list[dict[str, Any]]:
    """Load Tier B show rows from catalog/calibration_tier_b.json."""
    data = json.loads(path.read_text())
    shows = data.get("shows") or []
    if not isinstance(shows, list):
        raise ValueError(f"Expected shows list in {path}")
    return [dict(row) for row in shows]


def show_ids_for_split(rows: list[dict[str, Any]], split: str) -> list[str]:
    """Return show ids whose split field matches (train|holdout)."""
    wanted = split.strip().lower()
    return [str(r["id"]) for r in rows if str(r.get("split", "")).lower() == wanted]


def summarize_split_scores(
    rows: list[dict[str, Any]],
    *,
    track_delta_ok: int = 1,
) -> dict[str, Any]:
    """Aggregate F1 / track-count gate stats for one split's scored rows."""
    if not rows:
        return {
            "n": 0,
            "mean_f1": 0.0,
            "min_f1": 0.0,
            "track_count_ok_fraction": 0.0,
        }
    f1s = [float(r["f1"]) for r in rows]
    ok = sum(
        1 for r in rows if abs(int(r.get("track_count_delta", 99))) <= track_delta_ok
    )
    return {
        "n": len(rows),
        "mean_f1": sum(f1s) / len(f1s),
        "min_f1": min(f1s),
        "track_count_ok_fraction": ok / len(rows),
    }
