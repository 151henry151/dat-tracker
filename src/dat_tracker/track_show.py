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
    gap_fill_tracking_plan_cuts,
    refine_tracking_plan_cuts,
    request_tracking_plan_from_clips,
    resolve_escalate_model,
    speech_anchor_cuts_with_probes,
)
from dat_tracker.package import package_show_from_plan
from dat_tracker.refine_cuts import (
    adaptive_max_tracks,
    adaptive_min_separation_sec,
    adaptive_refine_half_window_sec,
    adaptive_speech_snap_look_ahead_sec,
    ensure_endpoint_cuts,
    merge_near_duplicate_cuts,
    overlong_gap_probe_centers,
    rebuild_tracks_from_cuts,
    snap_cuts_forward_to_speech,
    snap_cuts_to_nearby_listen_centers,
    snap_cuts_to_nearby_silence_ends,
    thin_cuts_to_max_tracks,
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


def resolve_speech_snap(*, refine: bool, speech_snap: bool | None) -> bool:
    """Default speech-snap off after refine (refine already targets new-track starts)."""
    if speech_snap is not None:
        return bool(speech_snap)
    return not refine


def should_run_gap_fill(
    *,
    cuts_sec: list[float],
    duration_sec: float,
    max_seg_sec: float = 480.0,
) -> bool:
    """True when the plan has a long segment or too few tracks for its length."""
    ordered = ensure_endpoint_cuts(cuts_sec, duration_sec=duration_sec)
    if len(ordered) < 2:
        return True
    max_seg = max(b - a for a, b in zip(ordered, ordered[1:], strict=False))
    track_count = len(ordered) - 1
    expected_min_tracks = max(4, int(round(duration_sec / 360.0)))
    return max_seg >= max_seg_sec or (
        track_count < expected_min_tracks and max_seg >= 300.0
    )


def should_escalate_to_pro(
    *,
    cuts_sec: list[float],
    duration_sec: float,
    max_seg_sec: float = 600.0,
) -> bool:
    """Escalate Flash→Pro only for clearly under-segmented longer shows.

    Short, already-dense plans (e.g. Sam Bush ~20 min) must not burn Pro just
    because one mid segment is a bit long.
    """
    if duration_sec < 1500.0:
        # Short shows: only escalate on extreme under-segmentation.
        ordered = ensure_endpoint_cuts(cuts_sec, duration_sec=duration_sec)
        if len(ordered) < 2:
            return True
        max_seg = max(b - a for a, b in zip(ordered, ordered[1:], strict=False))
        track_count = len(ordered) - 1
        expected_min_tracks = max(3, int(round(duration_sec / 360.0)))
        return track_count < expected_min_tracks and max_seg >= 480.0
    return should_run_gap_fill(
        cuts_sec=cuts_sec,
        duration_sec=duration_sec,
        max_seg_sec=max_seg_sec,
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
    refine_half_window_sec: float | None = None,
    speech_snap: bool | None = None,
    speech_snap_look_ahead_sec: float | None = None,
    gap_fill: bool = False,
    gap_fill_max_seg_sec: float = 480.0,
) -> dict[str, Any]:
    """Run sparse Gemini tracking and optionally export an etree-style package."""
    root = project_root or Path.cwd()
    paths = track_show_paths(work_root, show_id)
    paths["work_dir"].mkdir(parents=True, exist_ok=True)
    do_speech_snap = resolve_speech_snap(refine=refine, speech_snap=speech_snap)

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
    refine_window = (
        refine_half_window_sec
        if refine_half_window_sec is not None
        else adaptive_refine_half_window_sec(duration)
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
    escalate = should_escalate_to_pro(
        cuts_sec=list(plan.get("cuts_sec") or []),
        duration_sec=duration,
        max_seg_sec=max(gap_fill_max_seg_sec, 600.0),
    )
    escalate_model = resolve_escalate_model(project_root=root, escalate=escalate)
    # Gap-fill when explicitly requested, or automatically when under-segmented
    # (then use Pro for INSERT + refine).
    do_gap_fill = gap_fill or escalate
    if do_gap_fill and escalate:
        listen_pool = sorted(
            {
                float(c)
                for c in [
                    *anchors,
                    *probes,
                    *energy_cuts,
                    *silence_cuts,
                ]
            }
        )
        gap_probes = overlong_gap_probe_centers(
            list(plan.get("cuts_sec") or []),
            duration_sec=duration,
            candidate_centers=listen_pool,
            max_seg_sec=gap_fill_max_seg_sec,
            min_edge_sec=45.0,
            max_probes_per_gap=2,
        )
        if gap_probes:
            plan = gap_fill_tracking_plan_cuts(
                plan,
                source_audio=source_audio,
                work_dir=paths["work_dir"] / "gemini_gapfill",
                probe_centers_sec=gap_probes,
                # Gap-fill probes are often geometric estimates rather than a
                # precise candidate (see overlong_gap_probe_centers' proximity
                # fallback); a narrow ±12s clip missed real train boundaries
                # that landed 35-65s from the probe center. Widen the clip so
                # a plausible placement error still falls inside it.
                half_window_sec=max(45.0, half_window_sec),
                project_root=root,
                model=escalate_model,
            )
            plan = rebuild_tracks_from_cuts(
                plan,
                ensure_endpoint_cuts(
                    list(plan.get("cuts_sec") or []), duration_sec=duration
                ),
                note=(
                    f"Restored plan endpoints after gap-fill "
                    f"(model={escalate_model})."
                ),
            )
    elif gap_fill:
        existing_cuts = list(plan.get("cuts_sec") or [])
        if should_run_gap_fill(
            cuts_sec=existing_cuts,
            duration_sec=duration,
            max_seg_sec=gap_fill_max_seg_sec,
        ):
            listen_pool = sorted(
                {
                    float(c)
                    for c in [
                        *anchors,
                        *probes,
                        *energy_cuts,
                        *silence_cuts,
                    ]
                }
            )
            gap_probes = overlong_gap_probe_centers(
                existing_cuts,
                duration_sec=duration,
                candidate_centers=listen_pool,
                max_seg_sec=gap_fill_max_seg_sec,
                min_edge_sec=45.0,
                max_probes_per_gap=2,
            )
            if gap_probes:
                plan = gap_fill_tracking_plan_cuts(
                    plan,
                    source_audio=source_audio,
                    work_dir=paths["work_dir"] / "gemini_gapfill",
                    probe_centers_sec=gap_probes,
                    # Gap-fill probes are often geometric estimates rather
                    # than a precise candidate (see overlong_gap_probe_centers'
                    # proximity fallback); a narrow ±12s clip missed real
                    # train boundaries that landed 35-65s from the probe
                    # center. Widen the clip so a plausible placement error
                    # still falls inside it.
                    half_window_sec=max(45.0, half_window_sec),
                    project_root=root,
                )
                plan = rebuild_tracks_from_cuts(
                    plan,
                    ensure_endpoint_cuts(
                        list(plan.get("cuts_sec") or []), duration_sec=duration
                    ),
                    note="Restored plan endpoints after gap-fill.",
                )
    if refine:
        plan = refine_tracking_plan_cuts(
            plan,
            source_audio=source_audio,
            work_dir=paths["work_dir"] / "gemini_refine",
            half_window_sec=refine_window,
            project_root=root,
            model=escalate_model if escalate else None,
        )
        plan = rebuild_tracks_from_cuts(
            plan,
            ensure_endpoint_cuts(list(plan.get("cuts_sec") or []), duration_sec=duration),
            note=(
                "Restored plan endpoints after refine"
                + (f" (escalated model={escalate_model})." if escalate else ".")
            ),
        )
    if do_speech_snap:
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
    listen_centers = sorted({float(c) for c in [*anchors, *probes]})
    center_snapped = snap_cuts_to_nearby_listen_centers(
        list(plan.get("cuts_sec") or []),
        listen_centers=listen_centers,
        duration_sec=duration,
        radius_sec=40.0,
        min_delta_sec=8.0,
    )
    if center_snapped != list(plan.get("cuts_sec") or []):
        evidence = {
            c: [f"LISTEN_CENTER_SNAP@{c}"]
            for c in center_snapped[1:-1]
            if not any(abs(c - o) <= 0.05 for o in (plan.get("cuts_sec") or []))
        }
        plan = rebuild_tracks_from_cuts(
            plan,
            center_snapped,
            evidence_by_cut=evidence,
            note="Snapped clearly-offset mid cuts onto nearest listen centers (±40s).",
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
    max_tracks = adaptive_max_tracks(duration)
    if duration >= 2000.0:
        budgeted = thin_cuts_to_max_tracks(
            list(plan.get("cuts_sec") or []),
            max_tracks=max_tracks,
        )
        if budgeted != list(plan.get("cuts_sec") or []):
            plan = rebuild_tracks_from_cuts(
                plan,
                budgeted,
                note=(
                    f"Thinned long-show cuts to max {max_tracks} tracks "
                    f"by dropping tightly sandwiched mid cuts."
                ),
            )
    # Final endpoint normalize after all post-process snaps/thins.
    plan = rebuild_tracks_from_cuts(
        plan,
        ensure_endpoint_cuts(list(plan.get("cuts_sec") or []), duration_sec=duration),
        note="Final plan endpoint normalize.",
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
