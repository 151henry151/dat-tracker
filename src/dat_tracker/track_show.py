"""Orchestrate propose → Gemini listen → package for one continuous show."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from dat_tracker.boundaries import probe_duration_seconds, summarize_comparison
from dat_tracker.export_tracks import export_tracks_from_plan
from dat_tracker.gemini_tracker import (
    request_tracking_plan_from_clips,
    speech_anchor_cuts_with_probes,
)
from dat_tracker.package import package_show_from_plan
from dat_tracker.speech import parse_whisper_segments, transcribe_faster_whisper


def track_show_paths(work_root: Path, show_id: str) -> dict[str, Path]:
    """Standard work-tree paths for one show under data/work/."""
    work_dir = work_root / show_id
    return {
        "work_dir": work_dir,
        "plan": work_dir / "tracking_plan_gemini.json",
        "package_dir": work_dir / "package",
        "listen_dir": work_dir / "gemini_listen",
        "whisper_cache": work_dir / "whisper_segments.json",
    }


def ensure_whisper_cache(
    *,
    audio_path: Path,
    cache_path: Path,
    model_size: str = "base",
) -> dict[str, Any]:
    """Load cached Whisper JSON or transcribe once and write the cache."""
    if cache_path.is_file():
        return json.loads(cache_path.read_text())
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    payload = transcribe_faster_whisper(audio_path, model_size=model_size)
    cache_path.write_text(json.dumps(payload, indent=2) + "\n")
    return payload


def score_plan_against_known(
    *,
    known_cuts: list[float],
    plan: dict[str, Any],
    tolerance_sec: float = 15.0,
) -> dict[str, Any]:
    """Boundary F1 of plan cuts vs known cut list."""
    return summarize_comparison(
        reference_cuts=known_cuts,
        hypothesis_cuts=list(plan.get("cuts_sec") or []),
        tolerance_sec=tolerance_sec,
    )


def run_track_show(
    *,
    source_audio: Path,
    show_id: str,
    work_root: Path,
    artist: str,
    date: str,
    tracker: str = "Henry",
    venue: str | None = None,
    city: str | None = None,
    state: str | None = None,
    source_line: str | None = None,
    transfer: str | None = None,
    project_root: Path | None = None,
    whisper_model: str = "base",
    half_window_sec: float = 8.0,
    max_gap_sec: float = 240.0,
    probe_step_sec: float = 90.0,
    whisper_cache_path: Path | None = None,
    skip_package: bool = False,
) -> dict[str, Any]:
    """Run sparse Gemini tracking and optionally export an etree-style package."""
    root = project_root or Path.cwd()
    paths = track_show_paths(work_root, show_id)
    paths["work_dir"].mkdir(parents=True, exist_ok=True)

    cache_path = whisper_cache_path or paths["whisper_cache"]
    payload = ensure_whisper_cache(
        audio_path=source_audio,
        cache_path=cache_path,
        model_size=whisper_model,
    )
    segs = parse_whisper_segments(payload)
    duration = probe_duration_seconds(source_audio)
    anchors, probes = speech_anchor_cuts_with_probes(
        segs,
        duration_sec=duration,
        max_gap_sec=max_gap_sec,
        probe_step_sec=probe_step_sec,
    )

    try:
        rel_source = str(source_audio.resolve().relative_to(root.resolve()))
    except ValueError:
        rel_source = str(source_audio)

    plan = request_tracking_plan_from_clips(
        source_audio=source_audio,
        show_id=show_id,
        source_path=rel_source,
        duration_sec=duration,
        candidate_cuts_sec=anchors,
        probe_centers_sec=probes,
        work_dir=paths["listen_dir"],
        half_window_sec=half_window_sec,
        project_root=root,
    )
    paths["plan"].write_text(json.dumps(plan, indent=2) + "\n")

    result: dict[str, Any] = {
        "plan": plan,
        "paths": {k: str(v) for k, v in paths.items()},
        "anchors": anchors,
        "probes": probes,
        "track_paths": [],
        "package": None,
    }

    if not skip_package:
        track_paths = export_tracks_from_plan(
            source_audio, plan, paths["package_dir"]
        )
        packaged = package_show_from_plan(
            plan,
            track_paths=track_paths,
            out_dir=paths["package_dir"],
            artist=artist,
            date=date,
            tracker=tracker,
            venue=venue,
            city=city,
            state=state,
            source=source_line,
            transfer=transfer,
        )
        result["track_paths"] = [str(p) for p in track_paths]
        result["package"] = {k: str(v) for k, v in packaged.items()}

    return result
