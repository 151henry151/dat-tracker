"""Tests for progress helpers and Gemini clip-extract progress."""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import MagicMock, patch

from dat_tracker.progress_util import map_stage, progress_heartbeat


def test_map_stage_scales_local_fraction():
    seen: list[tuple[str, float]] = []
    mapped = map_stage(lambda m, f: seen.append((m, f)), start=0.4, end=0.6)
    assert mapped is not None
    mapped("x", 0.0)
    mapped("y", 0.5)
    mapped("z", 1.0)
    assert seen[0][1] == 0.4
    assert abs(seen[1][1] - 0.5) < 1e-9
    assert seen[2][1] == 0.6


def test_progress_heartbeat_emits_while_blocked():
    seen: list[str] = []

    def on_progress(message: str, fraction: float) -> None:
        seen.append(message)

    with progress_heartbeat(
        on_progress, "Waiting on API", fraction=0.7, interval_sec=0.15
    ):
        time.sleep(0.4)
    assert any("Waiting on API" in m for m in seen)
    assert any("elapsed" in m for m in seen)


def test_request_tracking_plan_reports_clip_progress(tmp_path: Path):
    from dat_tracker.gemini_tracker import request_tracking_plan_from_clips

    source = tmp_path / "src.flac"
    source.write_bytes(b"f")
    events: list[tuple[str, float]] = []

    fake_plan = {
        "schema_version": "1.0.0",
        "show_id": "demo",
        "source_path": "src.flac",
        "duration_sec": 100.0,
        "cuts_sec": [0.0, 50.0, 100.0],
        "tracks": [
            {
                "index": 1,
                "start_sec": 0.0,
                "end_sec": 50.0,
                "track_type": "song",
                "title": "A",
                "segue_into_next": False,
                "confidence": 0.5,
                "evidence": [],
            },
            {
                "index": 2,
                "start_sec": 50.0,
                "end_sec": 100.0,
                "track_type": "song",
                "title": "B",
                "segue_into_next": False,
                "confidence": 0.5,
                "evidence": [],
            },
        ],
        "overall_confidence": 0.5,
        "needs_review": False,
        "notes": [],
    }

    windows = [
        {"role": "candidate", "center_sec": 40.0, "start_sec": 28.0, "end_sec": 52.0},
        {"role": "candidate", "center_sec": 70.0, "start_sec": 58.0, "end_sec": 82.0},
    ]

    class FakeResp:
        text = ""
        candidates = []

    def fake_extract(source, dest, **kwargs):
        Path(dest).parent.mkdir(parents=True, exist_ok=True)
        Path(dest).write_bytes(b"f")

    with (
        patch(
            "dat_tracker.gemini_tracker.build_listen_windows",
            return_value=windows,
        ),
        patch(
            "dat_tracker.gemini_tracker.extract_audio_clip",
            side_effect=fake_extract,
        ),
        patch(
            "dat_tracker.gemini_tracker.tracking_listen_prompt",
            return_value="prompt",
        ),
        patch(
            "dat_tracker.gemini_tracker.load_train_few_shot_examples",
            return_value=[],
        ),
        patch("dat_tracker.gemini_tracker.resolve_gemini_api_key", return_value="k"),
        patch(
            "dat_tracker.gemini_tracker.resolve_gemini_model",
            return_value="gemini-test",
        ),
        patch("dat_tracker.gemini_tracker.parse_model_json", return_value=fake_plan),
        patch("dat_tracker.gemini_tracker.ensure_plan_tracks", side_effect=lambda p: p),
        patch("dat_tracker.gemini_tracker.validate_tracking_plan"),
        patch("dat_tracker.gemini_tracker._response_text", return_value="{}"),
        patch("google.genai.Client") as client_cls,
    ):
        client = MagicMock()
        client.models.generate_content.return_value = FakeResp()
        client_cls.return_value = client
        request_tracking_plan_from_clips(
            source_audio=source,
            show_id="demo",
            source_path="src.flac",
            duration_sec=100.0,
            candidate_cuts_sec=[40.0, 70.0],
            work_dir=tmp_path / "listen",
            on_progress=lambda m, f: events.append((m, f)),
        )

    assert any("clip" in m.lower() for m, _ in events)
    assert any("gemini" in m.lower() or "listen" in m.lower() for m, _ in events)


def test_run_track_show_classical_progress_does_not_rewind(tmp_path: Path):
    """After Whisper finishes at ~30%, classical stages must stay ≥ that."""
    from dat_tracker.track_show import run_track_show

    source = tmp_path / "a.flac"
    source.write_bytes(b"f")
    events: list[tuple[str, float]] = []

    def on_progress(message: str, fraction: float) -> None:
        events.append((message, fraction))

    def fake_whisper(**kwargs):
        cb = kwargs.get("on_progress")
        if cb:
            cb("Whisper transcription complete", 1.0)
        return {"segments": []}

    with (
        patch("dat_tracker.track_show.ensure_whisper_cache", side_effect=fake_whisper),
        patch("dat_tracker.track_show.parse_whisper_segments", return_value=[]),
        patch(
            "dat_tracker.track_show.probe_duration_seconds",
            side_effect=RuntimeError("stop-after-duration"),
        ),
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
            assert "stop-after-duration" in str(exc)

    assert events
    whisper_done = max(
        f for m, f in events if "complete" in m.lower() or "whisper" in m.lower()
    )
    post = [f for m, f in events if "duration" in m.lower() or "measuring" in m.lower()]
    assert post, events
    assert min(post) >= whisper_done - 1e-9


def test_prepare_plan_emits_progress(tmp_path: Path):
    from dat_tracker.review_cli import prepare_plan

    events: list[tuple[str, float]] = []
    raw = {
        "schema_version": "1.1.0",
        "show_id": "demo",
        "source_path": "x.flac",
        "duration_sec": 10.0,
        "cuts_sec": [0.0, 10.0],
        "tracks": [],
        "notes": [],
        "package": {},
        "review": {"status": "pending"},
    }
    with (
        patch("dat_tracker.review_cli.hydrate_plan_from_notes", side_effect=lambda p: p),
        patch(
            "dat_tracker.review_cli.hydrate_plan_from_companions",
            side_effect=lambda p, **kw: p,
        ),
        patch(
            "dat_tracker.review_cli.polish_package_metadata",
            side_effect=lambda p, **kw: p,
        ),
    ):
        prepare_plan(
            raw,
            project_root=tmp_path,
            on_progress=lambda m, f: events.append((m, f)),
        )
    assert any("hydrat" in m.lower() or "companion" in m.lower() for m, _ in events)
    assert events[-1][1] == 1.0


def test_build_package_reports_fraction_progress(tmp_path: Path):
    from dat_tracker.package_pipeline import build_package

    root = tmp_path
    (root / "data" / "out").mkdir(parents=True)
    (root / "data" / "work").mkdir(parents=True)
    source = root / "src.flac"
    source.write_bytes(b"f")
    plan = {
        "schema_version": "1.1.0",
        "show_id": "demo",
        "source_path": str(source),
        "duration_sec": 2.0,
        "cuts_sec": [0.0, 2.0],
        "tracks": [
            {
                "index": 1,
                "start_sec": 0.0,
                "end_sec": 2.0,
                "track_type": "song",
                "title": "A",
                "segue_into_next": False,
                "confidence": 0.5,
                "evidence": [],
            }
        ],
        "overall_confidence": 0.5,
        "needs_review": False,
        "notes": [],
        "package": {
            "artist": "A",
            "date": "2000-01-01",
            "tracker": "t",
            "venue": "",
            "city": "",
            "state": "",
            "source": "",
            "transfer": "",
            "transferer": "Cate Crowe",
            "set_label": "One Set",
        },
        "review": {
            "status": "approved",
            "approved_at": "2000-01-01T00:00:00Z",
            "approved_by": "t",
        },
    }
    events: list[tuple[str, float]] = []

    with (
        patch(
            "dat_tracker.package_pipeline.export_tracks_from_plan",
            return_value=[root / "data" / "out" / "demo" / "demo_t01.flac"],
        ) as export_mock,
        patch("dat_tracker.package_pipeline.apply_vorbis_tags"),
        patch(
            "dat_tracker.package_pipeline.package_show_from_plan",
            return_value={
                "txt": root / "data" / "out" / "demo" / "demo.txt",
                "ffp": root / "data" / "out" / "demo" / "demo.ffp.txt",
            },
        ),
        patch("dat_tracker.package_pipeline.shutil.copy2"),
    ):
        out = root / "data" / "out" / "demo"
        out.mkdir(parents=True)
        (out / "demo_t01.flac").write_bytes(b"f")
        (out / "demo.txt").write_text("x")
        (out / "demo.ffp.txt").write_text("y")
        build_package(
            plan,
            source_audio=source,
            project_root=root,
            on_progress=lambda m, f: events.append((m, f)),
        )
        assert export_mock.called
        assert export_mock.call_args.kwargs.get("on_progress") is not None

    assert events
    assert events[-1][1] == 1.0
    assert any("export" in m.lower() or "tag" in m.lower() for m, _ in events)
