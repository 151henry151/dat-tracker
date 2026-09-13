"""Mutate tracking-plan cuts and track fields for the review TUI."""

from __future__ import annotations

import copy
from typing import Any

from dat_tracker.refine_cuts import rebuild_tracks_from_cuts
from dat_tracker.review_plan import migrate_tracking_plan
from dat_tracker.tracking_plan import validate_tracking_plan

_TRACK_TYPES = {"song", "banter", "tuning", "intro", "encore_break", "unknown"}


def _preserve_track_meta(old_tracks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [dict(t) for t in old_tracks]


def _overlap_sec(a0: float, a1: float, b0: float, b1: float) -> float:
    return max(0.0, min(a1, b1) - max(a0, b0))


def _reapply_meta(
    plan: dict[str, Any],
    old_tracks: list[dict[str, Any]],
) -> dict[str, Any]:
    """Copy titles/types onto rebuilt tracks by time overlap (not by index).

    Index-based copy breaks when a cut is inserted: banter slots pick up the
    next song's title. After a split, only the fragment with the greatest
    overlap keeps the parent title; other fragments stay untitled.
    """
    tracks = list(plan.get("tracks") or [])
    if not old_tracks:
        plan["tracks"] = tracks
        return plan

    # new_idx -> (old_idx, overlap)
    assignment: list[tuple[int, float]] = []
    for track in tracks:
        start = float(track["start_sec"])
        end = float(track["end_sec"])
        best_i = -1
        best_ov = 0.0
        for i, prev in enumerate(old_tracks):
            ov = _overlap_sec(
                start, end, float(prev["start_sec"]), float(prev["end_sec"])
            )
            if ov > best_ov:
                best_ov = ov
                best_i = i
        assignment.append((best_i, best_ov))

    # Per old track: which new track won the largest overlap (keeps the title).
    title_winner: dict[int, int] = {}
    for new_i, (old_i, ov) in enumerate(assignment):
        if old_i < 0 or ov <= 0:
            continue
        prev = title_winner.get(old_i)
        if prev is None or ov > assignment[prev][1]:
            title_winner[old_i] = new_i

    for new_i, track in enumerate(tracks):
        old_i, ov = assignment[new_i]
        if old_i < 0 or ov <= 0:
            continue
        prev = old_tracks[old_i]
        track["track_type"] = prev.get("track_type") or track.get("track_type")
        track["segue_into_next"] = bool(prev.get("segue_into_next"))
        track["confidence"] = float(
            prev.get("confidence") or track.get("confidence") or 0.5
        )
        track["evidence"] = list(prev.get("evidence") or track.get("evidence") or [])
        if title_winner.get(old_i) == new_i:
            track["title"] = prev.get("title")
        else:
            # Split-off fragment — don't clone the song name.
            track["title"] = None
    plan["tracks"] = tracks
    return plan


def nudge_cut(
    plan: dict[str, Any],
    *,
    cut_index: int,
    delta_sec: float,
    min_separation_sec: float = 0.5,
) -> dict[str, Any]:
    """Move a mid cut by delta_sec; endpoints stay fixed."""
    plan = migrate_tracking_plan(plan)
    cuts = [float(c) for c in plan["cuts_sec"]]
    if cut_index <= 0 or cut_index >= len(cuts) - 1:
        return plan
    duration = float(plan["duration_sec"])
    lo = cuts[cut_index - 1] + min_separation_sec
    hi = cuts[cut_index + 1] - min_separation_sec
    new_t = max(lo, min(hi, cuts[cut_index] + float(delta_sec)))
    cuts[cut_index] = new_t
    old_meta = _preserve_track_meta(list(plan.get("tracks") or []))
    rebuilt = rebuild_tracks_from_cuts(
        plan, cuts, note=f"Nudged cut[{cut_index}] by {delta_sec:+.3f}s."
    )
    rebuilt = _reapply_meta(rebuilt, old_meta)
    rebuilt["cuts_sec"][0] = 0.0
    rebuilt["cuts_sec"][-1] = duration
    validate_tracking_plan(migrate_tracking_plan(rebuilt))
    return migrate_tracking_plan(rebuilt)


def insert_mid_cut(plan: dict[str, Any], *, at_sec: float) -> dict[str, Any]:
    plan = migrate_tracking_plan(plan)
    duration = float(plan["duration_sec"])
    at_sec = max(0.05, min(duration - 0.05, float(at_sec)))
    cuts = sorted({float(c) for c in plan["cuts_sec"]} | {at_sec})
    if abs(cuts[0]) > 1e-6:
        cuts = [0.0, *cuts]
    if abs(cuts[-1] - duration) > 1e-6:
        cuts.append(duration)
    old_meta = _preserve_track_meta(list(plan.get("tracks") or []))
    rebuilt = rebuild_tracks_from_cuts(
        plan, cuts, note=f"Inserted mid cut at {at_sec:.3f}s."
    )
    rebuilt = _reapply_meta(rebuilt, old_meta)
    return migrate_tracking_plan(rebuilt)


def delete_mid_cut(plan: dict[str, Any], *, cut_index: int) -> dict[str, Any]:
    plan = migrate_tracking_plan(plan)
    cuts = [float(c) for c in plan["cuts_sec"]]
    if cut_index <= 0 or cut_index >= len(cuts) - 1:
        return plan
    if len(cuts) <= 2:
        return plan
    del cuts[cut_index]
    old_meta = _preserve_track_meta(list(plan.get("tracks") or []))
    rebuilt = rebuild_tracks_from_cuts(
        plan, cuts, note=f"Deleted mid cut index {cut_index}."
    )
    rebuilt = _reapply_meta(rebuilt, old_meta)
    return migrate_tracking_plan(rebuilt)


def set_track_field(
    plan: dict[str, Any],
    *,
    track_index: int,
    title: str | None = None,
    track_type: str | None = None,
    segue_into_next: bool | None = None,
) -> dict[str, Any]:
    """Update metadata on track with 1-based index."""
    plan = migrate_tracking_plan(copy.deepcopy(plan))
    for track in plan.get("tracks") or []:
        if int(track["index"]) != int(track_index):
            continue
        if title is not None:
            track["title"] = title
        if track_type is not None:
            if track_type not in _TRACK_TYPES:
                raise ValueError(f"invalid track_type: {track_type}")
            track["track_type"] = track_type
        if segue_into_next is not None:
            track["segue_into_next"] = bool(segue_into_next)
        break
    validate_tracking_plan(plan)
    return plan


def set_package_field(plan: dict[str, Any], **fields: Any) -> dict[str, Any]:
    plan = migrate_tracking_plan(copy.deepcopy(plan))
    pkg = dict(plan.get("package") or {})
    for key, value in fields.items():
        if key not in pkg and key not in {
            "artist",
            "date",
            "venue",
            "city",
            "state",
            "source",
            "transfer",
            "transferer",
            "tracker",
            "collection_subjects",
            "set_label",
            "notes",
        }:
            continue
        pkg[key] = value
    plan["package"] = pkg
    validate_tracking_plan(plan)
    return plan
