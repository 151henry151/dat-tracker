"""Gap-fill INSERT must merge new mid cuts and keep endpoints."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from dat_tracker.gemini_tracker import gap_fill_tracking_plan_cuts


def test_gap_fill_tracking_plan_cuts_inserts_mid_cut(tmp_path: Path, monkeypatch):
    source = tmp_path / "show.flac"
    source.write_bytes(b"fake")
    plan = {
        "schema_version": "1.0.0",
        "show_id": "demo",
        "source_path": "demo.flac",
        "duration_sec": 1000.0,
        "cuts_sec": [0.0, 400.0, 1000.0],
        "tracks": [],
        "overall_confidence": 0.7,
        "needs_review": False,
        "notes": [],
    }

    def fake_extract(_src, dest, **_k):
        Path(dest).parent.mkdir(parents=True, exist_ok=True)
        Path(dest).write_bytes(b"clip")

    monkeypatch.setattr("dat_tracker.gemini_tracker.extract_audio_clip", fake_extract)
    monkeypatch.setattr(
        "dat_tracker.gemini_tracker.resolve_gemini_api_key", lambda **_k: "fake-key"
    )
    monkeypatch.setattr(
        "dat_tracker.gemini_tracker.resolve_gemini_model", lambda **_k: "fake-model"
    )
    monkeypatch.setattr("google.genai.Client", lambda *a, **k: object())

    def fake_generate(**_kwargs):
        return SimpleNamespace(
            text=json.dumps(
                {
                    "cuts_sec": [0.0, 400.0, 687.0, 1000.0],
                    "insert_decisions": [
                        {
                            "probe_sec": 690.0,
                            "insert_sec": 687.0,
                            "action": "INSERT",
                            "reason": "banter",
                        }
                    ],
                    "overall_confidence": 0.8,
                    "needs_review": False,
                }
            )
        )

    monkeypatch.setattr(
        "dat_tracker.gemini_tracker._generate_content_with_retries",
        fake_generate,
    )

    filled = gap_fill_tracking_plan_cuts(
        plan,
        source_audio=source,
        work_dir=tmp_path / "gapfill",
        probe_centers_sec=[690.0],
        project_root=tmp_path,
    )
    assert filled["cuts_sec"][0] == 0.0
    assert abs(filled["cuts_sec"][-1] - 1000.0) <= 0.05
    assert any(abs(c - 687.0) < 0.01 for c in filled["cuts_sec"])
