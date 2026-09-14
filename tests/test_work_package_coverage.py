"""Batch-check that every reviewable work show seeds non-blank package fields."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dat_tracker.review_discover import prefer_plan_path
from dat_tracker.review_hydrate import (
    find_companion_show_txt,
    hydrate_plan_from_notes,
    hydrate_titles_from_published_setlist,
    reconcile_track_count_to_published_setlist,
    seed_package_metadata,
)
from dat_tracker.review_package_polish import polish_package_metadata
from dat_tracker.review_plan import migrate_tracking_plan

_REPO = Path(__file__).resolve().parents[1]
_WORK = _REPO / "data" / "work"

_REQUIRED = ("artist", "date", "venue", "city", "state", "source", "transfer")


def _work_show_dirs() -> list[Path]:
    if not _WORK.is_dir():
        return []
    return sorted(
        p
        for p in _WORK.iterdir()
        if p.is_dir() and not p.name.startswith(".")
    )


def _stub_plan(show_id: str) -> dict:
    return migrate_tracking_plan(
        {
            "schema_version": "1.0.0",
            "show_id": show_id,
            "source_path": "x.flac",
            "duration_sec": 100.0,
            "cuts_sec": [0.0, 100.0],
            "tracks": [
                {
                    "index": 1,
                    "start_sec": 0.0,
                    "end_sec": 100.0,
                    "track_type": "unknown",
                    "title": None,
                    "segue_into_next": False,
                    "confidence": 0.5,
                    "evidence": [],
                }
            ],
            "overall_confidence": 0.5,
            "needs_review": False,
            "notes": [],
            "package": {},
        }
    )


def _seed_show(show_dir: Path) -> dict:
    show_id = show_dir.name
    plan_path = prefer_plan_path(show_dir)
    if plan_path is not None:
        raw = json.loads(plan_path.read_text())
        raw = dict(raw)
        raw["package"] = {}
        for track in raw.get("tracks") or []:
            track["title"] = None
        plan = migrate_tracking_plan(raw)
    else:
        plan = _stub_plan(show_id)
    plan = hydrate_plan_from_notes(plan)
    plan = reconcile_track_count_to_published_setlist(plan, project_root=_REPO)
    plan = hydrate_titles_from_published_setlist(plan, project_root=_REPO)
    plan = seed_package_metadata(
        plan, project_root=_REPO, use_llm_extract=False
    )
    return polish_package_metadata(plan, project_root=_REPO, use_llm=False)


@pytest.mark.skipif(not _WORK.is_dir(), reason="data/work not present")
@pytest.mark.parametrize("show_dir", _work_show_dirs(), ids=lambda p: p.name)
def test_work_show_package_fields_seed_from_companions(show_dir: Path):
    companion = find_companion_show_txt(show_dir.name, project_root=_REPO)
    if companion is None:
        pytest.skip(f"no companion txt for {show_dir.name}")
    plan = _seed_show(show_dir)
    pkg = plan.get("package") or {}
    blank = [k for k in _REQUIRED if not pkg.get(k)]
    summary = {k: pkg.get(k) for k in _REQUIRED}
    assert not blank, (
        f"{show_dir.name} blank package fields after seed: {blank}; "
        f"companion={companion.name}; pkg={summary!r}"
    )
