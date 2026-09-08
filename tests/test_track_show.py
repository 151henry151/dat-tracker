"""Tests for end-to-end track-show orchestration helpers."""

import json
from pathlib import Path

from dat_tracker.track_show import (
    ensure_whisper_cache,
    score_plan_against_known,
    track_show_paths,
)


def test_track_show_paths_nests_under_work(tmp_path: Path):
    paths = track_show_paths(tmp_path, "del2001-04-27.flac16")
    assert paths["work_dir"] == tmp_path / "del2001-04-27.flac16"
    assert paths["plan"].name == "tracking_plan_gemini.json"
    assert paths["package_dir"].name == "package"
    assert paths["whisper_cache"].name == "whisper_segments.json"


def test_score_plan_against_known_reports_f1():
    known = {"cuts_sec": [0.0, 10.0, 20.0]}
    plan = {"cuts_sec": [0.0, 10.5, 20.0]}
    metrics = score_plan_against_known(known_cuts=known["cuts_sec"], plan=plan, tolerance_sec=1.0)
    assert metrics["f1"] == 1.0
    assert metrics["hypothesis_tracks"] == 2


def test_ensure_whisper_cache_reuses_existing(tmp_path: Path, monkeypatch):
    cache = tmp_path / "whisper_segments.json"
    cache.write_text(json.dumps({"segments": [{"start": 1.0, "end": 2.0, "text": "hi"}]}) + "\n")

    def boom(*_a, **_k):
        raise AssertionError("should not transcribe")

    monkeypatch.setattr("dat_tracker.track_show.transcribe_faster_whisper", boom)
    payload = ensure_whisper_cache(
        audio_path=tmp_path / "missing.flac",
        cache_path=cache,
    )
    assert payload["segments"][0]["text"] == "hi"
