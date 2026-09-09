"""Refine must keep plan endpoints at 0 and duration."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from dat_tracker.gemini_tracker import refine_tracking_plan_cuts


def test_refine_tracking_plan_cuts_restores_missing_zero(tmp_path: Path, monkeypatch):
    """Gemini refine sometimes returns mid-cuts only; endpoints must be restored."""
    source = tmp_path / "show.flac"
    source.write_bytes(b"fake")

    plan = {
        "schema_version": "1.0.0",
        "show_id": "demo",
        "source_path": "demo.flac",
        "duration_sec": 1000.0,
        "cuts_sec": [0.0, 200.0, 500.0, 1000.0],
        "tracks": [],
        "overall_confidence": 0.7,
        "needs_review": False,
        "notes": [],
    }

    def fake_extract(_src, dest, **_k):
        Path(dest).parent.mkdir(parents=True, exist_ok=True)
        Path(dest).write_bytes(b"clip")

    monkeypatch.setattr(
        "dat_tracker.gemini_tracker.extract_audio_clip",
        fake_extract,
    )
    monkeypatch.setattr(
        "dat_tracker.gemini_tracker.resolve_gemini_api_key",
        lambda **_k: "fake-key",
    )
    monkeypatch.setattr(
        "dat_tracker.gemini_tracker.resolve_gemini_model",
        lambda **_k: "fake-model",
    )

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            pass

    monkeypatch.setattr(
        "google.genai.Client",
        _FakeClient,
    )

    def fake_generate(**_kwargs):
        # Omit 0.0 — the failure mode seen on train shows after refine.
        return SimpleNamespace(
            text=json.dumps(
                {
                    "schema_version": "1.0.0",
                    "show_id": "demo",
                    "duration_sec": 1000.0,
                    "cuts_sec": [43.4, 500.0, 1000.0],
                    "tracks": [],
                    "overall_confidence": 0.6,
                    "needs_review": False,
                    "refine_decisions": [],
                }
            )
        )

    monkeypatch.setattr(
        "dat_tracker.gemini_tracker._generate_content_with_retries",
        fake_generate,
    )

    refined = refine_tracking_plan_cuts(
        plan,
        source_audio=source,
        work_dir=tmp_path / "refine",
        project_root=tmp_path,
    )
    assert refined["cuts_sec"][0] == 0.0
    assert abs(refined["cuts_sec"][-1] - 1000.0) <= 0.05
    assert 43.4 in refined["cuts_sec"] or any(
        abs(c - 43.4) < 0.01 for c in refined["cuts_sec"]
    )
