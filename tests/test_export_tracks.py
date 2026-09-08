"""Tests for exporting FLAC tracks from a tracking plan."""

from pathlib import Path

import pytest

from dat_tracker.export_tracks import (
    etree_track_filename,
    export_tracks_from_plan,
    segment_specs_from_plan,
)


def test_etree_track_filename_uses_show_id_and_index():
    assert (
        etree_track_filename("del2001-04-27.flac16", 1, title=None)
        == "del2001-04-27.flac16_t01.flac"
    )
    assert (
        etree_track_filename("del2001-04-27.flac16", 2, title="Beauty of My Dreams")
        == "del2001-04-27.flac16_t02.flac"
    )


def test_segment_specs_from_plan_uses_tracks_array():
    plan = {
        "show_id": "del2001-04-27.flac16",
        "duration_sec": 100.0,
        "cuts_sec": [0.0, 40.0, 100.0],
        "tracks": [
            {
                "index": 1,
                "start_sec": 0.0,
                "end_sec": 40.0,
                "track_type": "song",
                "title": None,
            },
            {
                "index": 2,
                "start_sec": 40.0,
                "end_sec": 100.0,
                "track_type": "banter",
                "title": "Outro",
            },
        ],
    }
    specs = segment_specs_from_plan(plan)
    assert specs == [
        {
            "index": 1,
            "start_sec": 0.0,
            "end_sec": 40.0,
            "filename": "del2001-04-27.flac16_t01.flac",
            "title": None,
            "track_type": "song",
        },
        {
            "index": 2,
            "start_sec": 40.0,
            "end_sec": 100.0,
            "filename": "del2001-04-27.flac16_t02.flac",
            "title": "Outro",
            "track_type": "banter",
        },
    ]


def test_export_tracks_from_plan_writes_flac_segments(tmp_path: Path):
    import subprocess

    src = tmp_path / "continuous.flac"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:sample_rate=44100:duration=3",
            "-c:a",
            "flac",
            str(src),
        ],
        check=True,
        capture_output=True,
    )
    plan = {
        "schema_version": "1.0.0",
        "show_id": "demo2001-01-01",
        "source_path": str(src),
        "duration_sec": 3.0,
        "cuts_sec": [0.0, 1.0, 3.0],
        "tracks": [
            {
                "index": 1,
                "start_sec": 0.0,
                "end_sec": 1.0,
                "track_type": "song",
                "title": None,
                "segue_into_next": False,
                "confidence": 0.9,
                "evidence": [],
            },
            {
                "index": 2,
                "start_sec": 1.0,
                "end_sec": 3.0,
                "track_type": "song",
                "title": None,
                "segue_into_next": False,
                "confidence": 0.9,
                "evidence": [],
            },
        ],
        "overall_confidence": 0.9,
        "needs_review": False,
        "notes": [],
    }
    out_dir = tmp_path / "out"
    paths = export_tracks_from_plan(src, plan, out_dir)
    assert [p.name for p in paths] == [
        "demo2001-01-01_t01.flac",
        "demo2001-01-01_t02.flac",
    ]
    assert all(p.is_file() and p.stat().st_size > 0 for p in paths)
