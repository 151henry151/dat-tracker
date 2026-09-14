"""Tests for live tracking progress callbacks."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from dat_tracker.review_discover import ReviewableShow


def test_run_track_show_emits_progress_before_whisper(tmp_path: Path):
    from dat_tracker.track_show import run_track_show

    source = tmp_path / "a.flac"
    source.write_bytes(b"f")
    events: list[tuple[str, float]] = []

    def on_progress(message: str, fraction: float) -> None:
        events.append((message, fraction))

    with patch(
        "dat_tracker.track_show.ensure_whisper_cache",
        side_effect=RuntimeError("stop-after-progress"),
    ):
        try:
            run_track_show(
                source_audio=source,
                show_id="a",
                work_root=tmp_path / "work",
                artist="A",
                date="2000-01-01",
                skip_package=True,
                interactive_review=False,
                project_root=tmp_path,
                on_progress=on_progress,
            )
        except RuntimeError as exc:
            assert "stop-after-progress" in str(exc)

    assert events, "expected at least one progress event before Whisper"
    assert any("whisper" in m.lower() or "speech" in m.lower() for m, _ in events)
    assert 0.0 <= events[0][1] <= 1.0


def test_ensure_show_tracked_forwards_progress(tmp_path: Path):
    from dat_tracker.tui_review.session import ensure_show_tracked

    show = ReviewableShow(
        show_id="x",
        plan_path=tmp_path / "work" / "x" / "tracking_plan_gemini.json",
        source_path=tmp_path / "x.flac",
        review_status="untracked",
        track_count=0,
        duration_sec=None,
        work_dir=tmp_path / "work" / "x",
        needs_tracking=True,
        relative_path="x.flac",
        artist="A",
        date="2001-01-01",
    )
    (tmp_path / "x.flac").write_bytes(b"f")
    seen: list[tuple[str, float]] = []

    def fake_run(**kwargs):
        assert callable(kwargs.get("on_progress"))
        kwargs["on_progress"]("Gemini listen…", 0.5)
        plan = {
            "show_id": "x",
            "cuts_sec": [0.0, 1.0],
            "tracks": [],
            "duration_sec": 1.0,
            "review": {"status": "pending"},
        }
        path = kwargs["work_root"] / "x" / "tracking_plan_gemini.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        import json

        path.write_text(json.dumps(plan) + "\n")
        return {"plan": plan, "paths": {"plan": str(path)}}

    with patch("dat_tracker.track_show.run_track_show", fake_run):
        ensure_show_tracked(
            show,
            project_root=tmp_path,
            on_progress=lambda m, f: seen.append((m, f)),
        )
    assert seen == [("Gemini listen…", 0.5)]
