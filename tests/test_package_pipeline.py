"""Tests for end-to-end build_package (export + tags + txt/ffp)."""

from __future__ import annotations

import subprocess
from pathlib import Path

from dat_tracker.review_plan import migrate_tracking_plan
from dat_tracker.tracking_plan import validate_tracking_plan


def _tone_flac(path: Path, *, duration: float = 1.0, freq: int = 440) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency={freq}:sample_rate=44100:duration={duration}",
            "-c:a",
            "flac",
            str(path),
        ],
        check=True,
        capture_output=True,
    )
    return path


def _approved_plan(show_id: str, source: Path) -> dict:
    plan = migrate_tracking_plan(
        {
            "schema_version": "1.0.0",
            "show_id": show_id,
            "source_path": str(source),
            "duration_sec": 2.0,
            "cuts_sec": [0.0, 1.0, 2.0],
            "tracks": [
                {
                    "index": 1,
                    "start_sec": 0.0,
                    "end_sec": 1.0,
                    "track_type": "song",
                    "title": "Song One",
                    "segue_into_next": False,
                    "confidence": 0.9,
                    "evidence": [],
                },
                {
                    "index": 2,
                    "start_sec": 1.0,
                    "end_sec": 2.0,
                    "track_type": "song",
                    "title": "Song Two",
                    "segue_into_next": False,
                    "confidence": 0.9,
                    "evidence": [],
                },
            ],
            "overall_confidence": 0.9,
            "needs_review": False,
            "notes": [],
            "package": {
                "artist": "Test Band",
                "date": "2001-04-27",
                "venue": "Test Venue",
                "city": "Wilkesboro",
                "state": "NC",
                "source": "SBD > DAT",
                "transfer": "DAT > FLAC",
                "transferer": "Cate Crowe",
                "tracker": "Tester",
                "set_label": "One Set",
                "collection_subjects": ["Brian H Collection"],
                "notes": None,
            },
            "review": {
                "status": "approved",
                "approved_at": "2026-01-01T00:00:00+00:00",
                "approved_by": "Tester",
                "method": "accept_all",
            },
        }
    )
    validate_tracking_plan(plan)
    return plan


def test_build_package_writes_out_and_work_mirror(tmp_path: Path):
    from mutagen.flac import FLAC

    from dat_tracker.package_pipeline import build_package

    root = tmp_path
    show_id = "demo2001-04-27"
    source = _tone_flac(root / "continuous.flac", duration=2.0)
    plan = _approved_plan(show_id, source)

    result = build_package(plan, source_audio=source, project_root=root)

    out_dir = root / "data" / "out" / show_id
    work_dir = root / "data" / "work" / show_id / "package"
    assert result.out_dir == out_dir
    assert result.track_count == 2
    assert (out_dir / f"{show_id}_t01.flac").is_file()
    assert (out_dir / f"{show_id}_t02.flac").is_file()
    assert (out_dir / f"{show_id}.txt").is_file()
    assert (out_dir / "fingerprint.ffp.txt").is_file()
    assert (work_dir / f"{show_id}_t01.flac").is_file()
    assert (work_dir / f"{show_id}.txt").is_file()

    audio = FLAC(out_dir / f"{show_id}_t01.flac")
    assert audio["artist"] == ["Test Band"]
    assert audio["title"] == ["Song One"]
    assert audio["tracknumber"] == ["1"]
    assert audio["date"] == ["2001-04-27"]
