"""Tests for discovering reviewable shows under data/work."""

from __future__ import annotations

import json
from pathlib import Path

from dat_tracker.review_discover import (
    discover_reviewable_shows,
    prefer_plan_path,
    resolve_show_for_review,
    resolve_source_audio,
)


def _write_plan(path: Path, *, show_id: str, source: str, status: str = "pending") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": "1.1.0",
                "show_id": show_id,
                "source_path": source,
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
                "package": {},
                "review": {
                    "status": status,
                    "approved_at": None,
                    "approved_by": None,
                    "method": None,
                },
            }
        )
        + "\n"
    )


def test_prefer_plan_path_gemini_first(tmp_path: Path):
    work = tmp_path / "show"
    work.mkdir()
    (work / "tracking_plan.json").write_text("{}")
    gem = work / "tracking_plan_gemini.json"
    gem.write_text("{}")
    assert prefer_plan_path(work) == gem


def test_prefer_plan_path_skips_as_delivered(tmp_path: Path):
    work = tmp_path / "show"
    work.mkdir()
    (work / "tracking_plan_as_delivered.json").write_text("{}")
    gem = work / "tracking_plan_gemini.json"
    gem.write_text("{}")
    assert prefer_plan_path(work) == gem


def test_resolve_source_audio_relative_and_fallback(tmp_path: Path):
    root = tmp_path
    src = root / "data" / "calibration" / "demo" / "synthetic_continuous.flac"
    src.parent.mkdir(parents=True)
    src.write_bytes(b"flac")
    # Relative path from plan.
    assert resolve_source_audio(
        "data/calibration/demo/synthetic_continuous.flac",
        project_root=root,
        show_id="demo",
    ) == src
    # Fallback when plan path missing.
    assert resolve_source_audio(
        "missing.flac",
        project_root=root,
        show_id="demo",
    ) == src


def test_discover_reviewable_shows(tmp_path: Path):
    root = tmp_path
    work = root / "data" / "work"
    audio = root / "data" / "calibration" / "aaa" / "synthetic_continuous.flac"
    audio.parent.mkdir(parents=True)
    audio.write_bytes(b"x")
    _write_plan(
        work / "aaa" / "tracking_plan_gemini.json",
        show_id="aaa",
        source=str(audio),
        status="pending",
    )
    _write_plan(
        work / "bbb" / "tracking_plan_gemini.json",
        show_id="bbb",
        source="missing.flac",
        status="approved",
    )
    shows = discover_reviewable_shows(project_root=root)
    assert [s.show_id for s in shows] == ["aaa", "bbb"]
    assert shows[0].review_status == "pending"
    assert shows[0].track_count == 2
    assert shows[0].source_path == audio
    assert shows[0].has_audio is True
    assert shows[1].has_audio is False


def test_resolve_show_for_review_by_id(tmp_path: Path):
    root = tmp_path
    work = root / "data" / "work"
    audio = root / "data" / "calibration" / "sbb" / "synthetic_continuous.flac"
    audio.parent.mkdir(parents=True)
    audio.write_bytes(b"x")
    plan = work / "sbb" / "tracking_plan_gemini.json"
    _write_plan(plan, show_id="sbb", source=str(audio))
    found = resolve_show_for_review("sbb", project_root=root)
    assert found is not None
    assert found.plan_path == plan
    assert found.source_path == audio


def test_cli_accept_all_by_show_id(tmp_path: Path):
    from dat_tracker.review_cli import main

    root = tmp_path
    work = root / "data" / "work"
    audio = root / "data" / "calibration" / "sbb" / "synthetic_continuous.flac"
    audio.parent.mkdir(parents=True)
    audio.write_bytes(b"x")
    plan = work / "sbb" / "tracking_plan_gemini.json"
    _write_plan(plan, show_id="sbb", source=str(audio), status="pending")
    code = main(
        [
            "--root",
            str(root),
            "--accept-all",
            "sbb",
        ]
    )
    assert code == 0
    doc = json.loads(plan.read_text())
    assert doc["review"]["status"] == "approved"
