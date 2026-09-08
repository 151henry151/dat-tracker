"""Orchestrate propose → Gemini listen → package for one continuous show."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from dat_tracker.boundaries import probe_duration_seconds, summarize_comparison
from dat_tracker.energy import propose_cuts_from_audio
from dat_tracker.silence import run_silencedetect, silence_end_candidates
from dat_tracker.export_tracks import export_tracks_from_plan
from dat_tracker.gemini_tracker import (
    refine_tracking_plan_cuts,
    request_tracking_plan_from_clips,
    speech_anchor_cuts_with_probes,
)
from dat_tracker.package import package_show_from_plan
from dat_tracker.refine_cuts import (
    adaptive_min_separation_sec,
    adaptive_speech_snap_look_ahead_sec,
    ensure_endpoint_cuts,
    merge_near_duplicate_cuts,
    rebuild_tracks_from_cuts,
    snap_cuts_forward_to_speech,
    snap_cuts_to_nearby_silence_ends,
    thin_listen_centers,
)
from dat_tracker.speech import (
    filter_plausible_speech_segments,
    merge_speech_islands,
    parse_whisper_segments,
    transcribe_faster_whisper,
)


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
    refine: bool = False,
    refine_half_window_sec: float = 20.0,
    speech_snap: bool = True,
    speech_snap_look_ahead_sec: float | None = None,
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
    energy_cuts = propose_cuts_from_audio(source_audio, min_separation_sec=60.0)
    silence_cuts = silence_end_candidates(
        run_silencedetect(source_audio, noise_db=-40, min_silence_sec=1.2),
        min_silence_sec=1.2,
    )
    anchors, probes = speech_anchor_cuts_with_probes(
        segs,
        duration_sec=duration,
        max_gap_sec=max_gap_sec,
        probe_step_sec=probe_step_sec,
        energy_cuts=energy_cuts,
        silence_cuts=silence_cuts,
    )
    anchors, probes = thin_listen_centers(
        anchors=anchors,
        probes=probes,
        duration_sec=duration,
    )
    snap_look_ahead = (
        speech_snap_look_ahead_sec
        if speech_snap_look_ahead_sec is not None
        else adaptive_speech_snap_look_ahead_sec(duration)
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
    plan = rebuild_tracks_from_cuts(
        plan,
        ensure_endpoint_cuts(list(plan.get("cuts_sec") or []), duration_sec=duration),
        note="Normalized plan endpoints to 0 and duration.",
    )
    if refine:
        plan = refine_tracking_plan_cuts(
            plan,
            source_audio=source_audio,
            work_dir=paths["work_dir"] / "gemini_refine",
            half_window_sec=refine_half_window_sec,
            project_root=root,
        )
    if speech_snap:
        islands = merge_speech_islands(
            filter_plausible_speech_segments(segs, max_seg_sec=20.0)
        )
        snapped = snap_cuts_forward_to_speech(
            list(plan.get("cuts_sec") or []),
            speech_islands=islands,
            duration_sec=duration,
            look_ahead_sec=snap_look_ahead,
        )
        evidence = {
            c: [f"SPEECH_SNAP_FORWARD@{c}"]
            for c in snapped[1:-1]
            if not any(abs(c - o) <= 0.05 for o in (plan.get("cuts_sec") or []))
        }
        plan = rebuild_tracks_from_cuts(
            plan,
            snapped,
            evidence_by_cut=evidence,
            note="Snapped mid cuts forward to last speech onset in look-ahead window.",
        )
    silence_snapped = snap_cuts_to_nearby_silence_ends(
        list(plan.get("cuts_sec") or []),
        silence_ends=silence_cuts,
        duration_sec=duration,
        look_back_sec=55.0,
        look_ahead_sec=10.0,
    )
    if silence_snapped != list(plan.get("cuts_sec") or []):
        evidence = {
            c: [f"SILENCE_SNAP@{c}"]
            for c in silence_snapped[1:-1]
            if not any(abs(c - o) <= 0.05 for o in (plan.get("cuts_sec") or []))
        }
        plan = rebuild_tracks_from_cuts(
            plan,
            silence_snapped,
            evidence_by_cut=evidence,
            note="Snapped clearly-late mid cuts back onto silence ends (≥20s late, ≤55s look-back).",
        )
    dedupe_sep = adaptive_min_separation_sec(duration)
    deduped = merge_near_duplicate_cuts(
        list(plan.get("cuts_sec") or []),
        min_separation_sec=dedupe_sep,
    )
    if deduped != list(plan.get("cuts_sec") or []):
        plan = rebuild_tracks_from_cuts(
            plan,
            deduped,
            note=(
                f"Merged near-duplicate cuts with adaptive min separation "
                f"{dedupe_sep:.0f}s (kept later time in each cluster)."
            ),
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
