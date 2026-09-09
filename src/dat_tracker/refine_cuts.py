"""Second-pass cut refinement: snap to where the next track begins."""

from __future__ import annotations

import json
from typing import Any


def rebuild_tracks_from_cuts(
    plan: dict[str, Any],
    cuts_sec: list[float],
    *,
    evidence_by_cut: dict[float, list[str]] | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    """Rewrite plan cuts/tracks from a new cut list; keep titles by index order."""
    ordered = sorted(float(c) for c in cuts_sec)
    old_tracks = sorted(plan.get("tracks") or [], key=lambda t: int(t["index"]))
    evidence_by_cut = evidence_by_cut or {}
    tracks: list[dict[str, Any]] = []
    for i, (start, end) in enumerate(zip(ordered, ordered[1:], strict=False), start=1):
        prior = old_tracks[i - 1] if i - 1 < len(old_tracks) else {}
        extra = []
        for cut, notes in evidence_by_cut.items():
            if abs(cut - start) <= 0.05:
                extra.extend(notes)
        tracks.append(
            {
                "index": i,
                "start_sec": start,
                "end_sec": end,
                "track_type": prior.get("track_type") or "unknown",
                "title": prior.get("title"),
                "segue_into_next": bool(prior.get("segue_into_next", False)),
                "confidence": float(prior.get("confidence") or 0.5),
                "evidence": list(prior.get("evidence") or []) + extra,
            }
        )
    out = dict(plan)
    out["cuts_sec"] = ordered
    out["tracks"] = tracks
    if note:
        notes = list(out.get("notes") or [])
        notes.append(note)
        out["notes"] = notes
    return out


def snap_cuts_forward_to_speech(
    cuts_sec: list[float],
    *,
    speech_islands: list[dict[str, Any]],
    duration_sec: float,
    look_ahead_sec: float = 45.0,
) -> list[float]:
    """Move mid cuts forward to the last speech onset in a short look-ahead window.

    Many published packages start the next track on the post-song banter / song
    announcement rather than on the previous song's last note.
    """
    onsets = sorted(float(i["start"]) for i in speech_islands)
    ordered = sorted(float(c) for c in cuts_sec)
    if not ordered:
        return []
    out = [ordered[0]]
    for cut in ordered[1:-1]:
        candidates = [o for o in onsets if cut < o <= cut + look_ahead_sec]
        out.append(candidates[-1] if candidates else cut)
    out.append(ordered[-1] if abs(ordered[-1] - duration_sec) <= 0.05 else float(duration_sec))
    # Ensure monotonic non-decreasing with tiny epsilon collapse.
    mono: list[float] = [out[0]]
    for c in out[1:]:
        if c < mono[-1] + 0.05:
            continue
        mono.append(c)
    if abs(mono[-1] - duration_sec) > 0.05:
        mono.append(float(duration_sec))
    return mono


def snap_clearly_early_cuts_to_speech(
    cuts_sec: list[float],
    *,
    speech_islands: list[dict[str, Any]],
    duration_sec: float,
    min_early_sec: float = 15.0,
    max_early_sec: float = 35.0,
    already_near_sec: float = 5.0,
) -> list[float]:
    """Snap mid cuts that sit clearly early (in applause) to the next speech onset.

    Unlike the broad forward speech snap, this only moves a cut when:
    - the cut is *not* already within already_near_sec of any speech onset, and
    - the nearest speech onset is 15–35s ahead.

    That targets "cut on last note / mid-applause" without yanking a correct
    song-start cut into mid-song vocals. Prefers the *first* onset in window.
    """
    onsets = sorted(float(i["start"]) for i in speech_islands)
    ordered = sorted(float(c) for c in cuts_sec)
    if not ordered:
        return []
    out = [ordered[0]]
    for cut in ordered[1:-1]:
        if any(abs(o - cut) <= already_near_sec for o in onsets):
            out.append(cut)
            continue
        candidates = [
            o for o in onsets if cut + min_early_sec <= o <= cut + max_early_sec
        ]
        out.append(candidates[0] if candidates else cut)
    out.append(
        ordered[-1] if abs(ordered[-1] - duration_sec) <= 0.05 else float(duration_sec)
    )
    mono: list[float] = [out[0]]
    for c in out[1:]:
        if c < mono[-1] + 0.05:
            continue
        mono.append(c)
    if abs(mono[-1] - duration_sec) > 0.05:
        mono.append(float(duration_sec))
    return mono


def snap_cuts_to_nearby_silence_ends(
    cuts_sec: list[float],
    *,
    silence_ends: list[float],
    duration_sec: float,
    look_back_sec: float = 55.0,
    look_ahead_sec: float = 10.0,
    min_late_sec: float = 20.0,
    radius_sec: float | None = None,
) -> list[float]:
    """Pull clearly-late mid cuts back onto a recent silence end.

    Only snaps when a silence end lies at least min_late_sec before the cut
    (within look_back_sec). That corrects Gemini's common ~30–50s-late
    placements without nudging already-close cuts onto the wrong gap.
    """
    if radius_sec is not None:
        look_back_sec = float(radius_sec)
    ends = sorted(float(s) for s in silence_ends)
    ordered = sorted(float(c) for c in cuts_sec)
    if not ordered:
        return []
    out = [ordered[0]]
    for cut in ordered[1:-1]:
        near = [
            s
            for s in ends
            if cut - look_back_sec <= s <= cut - min_late_sec
        ]
        # Latest silence end in the late window (closest from behind).
        out.append(max(near) if near else cut)
    out.append(
        ordered[-1] if abs(ordered[-1] - duration_sec) <= 0.05 else float(duration_sec)
    )
    mono: list[float] = [out[0]]
    for c in out[1:]:
        if c < mono[-1] + 0.05:
            continue
        mono.append(c)
    if abs(mono[-1] - duration_sec) > 0.05:
        mono.append(float(duration_sec))
    return mono


def snap_cuts_to_nearby_listen_centers(
    cuts_sec: list[float],
    *,
    listen_centers: list[float],
    duration_sec: float,
    radius_sec: float = 40.0,
    min_delta_sec: float = 8.0,
) -> list[float]:
    """Snap clearly-offset mid cuts onto the nearest listen center in radius.

    Gemini often lands 20–40s off a real transition that was already proposed as
    a speech/energy listen center. Pulling those mid cuts onto the nearest
    center (only when farther than min_delta_sec) corrects near-misses without
    thrashing already-close placements.
    """
    centers = sorted(float(c) for c in listen_centers)
    ordered = sorted(float(c) for c in cuts_sec)
    if not ordered:
        return []
    out = [ordered[0]]
    for cut in ordered[1:-1]:
        near = [(abs(c - cut), c) for c in centers if abs(c - cut) <= radius_sec]
        if near:
            delta, center = min(near, key=lambda t: t[0])
            out.append(center if delta >= min_delta_sec else cut)
        else:
            out.append(cut)
    out.append(
        ordered[-1] if abs(ordered[-1] - duration_sec) <= 0.05 else float(duration_sec)
    )
    mono: list[float] = [out[0]]
    for c in out[1:]:
        if c < mono[-1] + 0.05:
            continue
        mono.append(c)
    if abs(mono[-1] - duration_sec) > 0.05:
        mono.append(float(duration_sec))
    return mono


def merge_near_duplicate_cuts(
    cuts_sec: list[float],
    *,
    min_separation_sec: float = 20.0,
) -> list[float]:
    """Collapse cut clusters closer than min_separation_sec, keeping the later time.

    Preferring the later cut matches etree “start of next track” packaging when
    Gemini emits both song-end and banter-start a few seconds apart.
    """
    ordered = sorted(float(c) for c in cuts_sec)
    if not ordered:
        return []
    out = [ordered[0]]
    for cut in ordered[1:]:
        if cut - out[-1] < min_separation_sec:
            out[-1] = cut
        else:
            out.append(cut)
    return out


def adaptive_min_separation_sec(duration_sec: float) -> float:
    """Wider cut spacing on long shows to curb mid-song over-segmentation."""
    if duration_sec >= 3000.0:
        return 90.0
    if duration_sec >= 1200.0:
        return 45.0
    return 20.0


def adaptive_refine_half_window_sec(duration_sec: float) -> float:
    """Widen refine clips on longer shows so ±15–40s placement errors are audible."""
    if duration_sec >= 4000.0:
        return 60.0
    if duration_sec >= 2000.0:
        return 50.0
    if duration_sec >= 1200.0:
        return 40.0
    return 20.0


def adaptive_max_tracks(duration_sec: float) -> int:
    """Soft upper bound on track count (~4 min average, including banter tracks)."""
    return max(4, int(round(float(duration_sec) / 240.0)))


def thin_cuts_to_max_tracks(
    cuts_sec: list[float],
    *,
    max_tracks: int,
) -> list[float]:
    """Drop the most tightly sandwiched mid cuts until track count fits.

    Over-dense Gemini accepts on long jam sets create brief false tracks. Removing
    interior cuts with the smallest neighboring gap prefers merging those shorts
    without deleting well-spaced song boundaries.
    """
    ordered = sorted(float(c) for c in cuts_sec)
    if len(ordered) < 2:
        return ordered
    while len(ordered) - 1 > max_tracks:
        best_i = None
        best_score = float("inf")
        for i in range(1, len(ordered) - 1):
            left = ordered[i] - ordered[i - 1]
            right = ordered[i + 1] - ordered[i]
            score = min(left, right)
            if score < best_score:
                best_score = score
                best_i = i
        if best_i is None:
            break
        ordered.pop(best_i)
    return ordered


def adaptive_speech_snap_look_ahead_sec(duration_sec: float) -> float:
    """Forward speech-snap windows; keep modest so mid-song speech is not preferred."""
    if duration_sec >= 2000.0:
        return 45.0
    return 30.0


def ensure_endpoint_cuts(cuts_sec: list[float], *, duration_sec: float) -> list[float]:
    """Guarantee cuts start at 0 and end at duration_sec."""
    ordered = sorted(float(c) for c in cuts_sec)
    if not ordered or ordered[0] > 0.05:
        ordered = [0.0, *ordered]
    if abs(ordered[-1] - duration_sec) > 0.05:
        ordered.append(float(duration_sec))
    # Dedupe exact-ish duplicates.
    out = [ordered[0]]
    for c in ordered[1:]:
        if c - out[-1] > 0.05:
            out.append(c)
    return out


def overlong_gap_probe_centers(
    cuts_sec: list[float],
    *,
    duration_sec: float,
    candidate_centers: list[float],
    max_seg_sec: float = 420.0,
    min_edge_sec: float = 45.0,
    max_probes_per_gap: int = 3,
) -> list[float]:
    """Pick listen centers inside track segments longer than max_seg_sec.

    Used for a second Gemini INSERT pass when the first plan under-segments.
    Prefers existing speech/energy candidates nearest to evenly spaced targets.
    """
    ordered = ensure_endpoint_cuts(cuts_sec, duration_sec=duration_sec)
    candidates = sorted(float(c) for c in candidate_centers)
    out: list[float] = []
    for left, right in zip(ordered, ordered[1:], strict=False):
        gap = right - left
        if gap <= max_seg_sec:
            continue
        n_need = min(max_probes_per_gap, max(1, int(gap // max_seg_sec)))
        mids = [
            c
            for c in candidates
            if left + min_edge_sec < c < right - min_edge_sec
        ]
        if not mids:
            # Fall back to geometric midpoints when no classical candidates exist.
            for i in range(n_need):
                out.append(left + gap * (i + 1) / (n_need + 1))
            continue
        targets = [left + gap * (i + 1) / (n_need + 1) for i in range(n_need)]
        used: list[float] = []
        for target in targets:
            best = None
            best_d = None
            for c in mids:
                if any(abs(c - u) < 30.0 for u in used):
                    continue
                d = abs(c - target)
                if best_d is None or d < best_d:
                    best, best_d = c, d
            if best is not None:
                used.append(best)
                out.append(best)
    return sorted({round(c, 3) for c in out})


def merge_gap_fill_cuts(
    existing_cuts: list[float],
    proposed_cuts: list[float],
    *,
    duration_sec: float,
    min_separation_sec: float = 25.0,
) -> list[float]:
    """Union existing plan cuts with newly inserted mid cuts; keep endpoints."""
    ordered = ensure_endpoint_cuts(
        [*existing_cuts, *proposed_cuts],
        duration_sec=duration_sec,
    )
    out = [ordered[0]]
    for c in ordered[1:-1]:
        if c - out[-1] >= min_separation_sec:
            out.append(c)
    if ordered[-1] - out[-1] >= 0.05:
        out.append(ordered[-1])
    return ensure_endpoint_cuts(out, duration_sec=duration_sec)


def thin_listen_centers(
    *,
    anchors: list[float],
    probes: list[float],
    duration_sec: float,
    target_mid_cuts: int | None = None,
) -> tuple[list[float], list[float]]:
    """Keep speech anchors; thin only gap probes on long shows.

    Dense banter often coexists with true song-boundary speech. Dropping mid
    anchors to hit a 4-minute budget removed real cuts on long jam sets, so
    anchors are preserved. Cap probes on long shows so Gemini is not flooded
    with mid-song energy peaks.
    """
    if target_mid_cuts is None:
        target_mid_cuts = max(4, int(round(duration_sec / 240.0)))

    ordered = sorted({float(a) for a in anchors})
    if not ordered or ordered[0] > 0.05:
        ordered = [0.0, *ordered]
    if abs(ordered[-1] - duration_sec) > 0.05:
        ordered.append(float(duration_sec))

    mid = [a for a in ordered if 0.05 < a < duration_sec - 0.05]
    thinned_anchors = [0.0, *mid, float(duration_sec)]
    if duration_sec < 2000.0:
        return thinned_anchors, sorted({float(p) for p in probes})

    max_probes = max(2, target_mid_cuts)
    kept_probes: list[float] = []
    for left, right in zip(thinned_anchors, thinned_anchors[1:], strict=False):
        if right - left < 240.0:
            continue
        in_gap = [
            float(p)
            for p in probes
            if left + 20.0 < float(p) < right - 20.0
        ]
        in_gap.sort(key=lambda p: abs(p - (left + right) / 2.0))
        for p in in_gap[:2]:
            if not any(abs(p - q) <= 5.0 for q in kept_probes):
                kept_probes.append(p)
            if len(kept_probes) >= max_probes:
                break
        if len(kept_probes) >= max_probes:
            break
    return thinned_anchors, sorted(kept_probes)


def refine_listen_prompt(
    *,
    show_id: str,
    duration_sec: float,
    proposed_cuts_sec: list[float],
    windows: list[dict[str, Any]],
) -> str:
    """Prompt: move each mid cut to where the *next* track begins."""
    win_lines = "\n".join(
        f"- around proposed cut {float(w['center_sec']):.3f}s "
        f"(clip covers {float(w['start_sec']):.3f}–{float(w['end_sec']):.3f}s)"
        for w in windows
    )
    return f"""You already proposed track cuts for a live show. Refine them.

Show id: {show_id}
Master duration: {duration_sec:.3f}s
Proposed cuts (including endpoints): {json.dumps(proposed_cuts_sec)}

Etree packaging usually starts the *next* track where the new song or banter
begins — often after trailing applause that still belongs on the previous track.
Do NOT place the cut on the previous song's last note if applause or dead air
still belongs with that song. Place it where the new track begins.

You get a short clip around each mid-show proposed cut:
{win_lines}

Return ONLY JSON:
{{
  "schema_version": "1.0.0",
  "show_id": "{show_id}",
  "source_path": "PLACEHOLDER",
  "duration_sec": {duration_sec:.3f},
  "cuts_sec": [0.0, ... , {duration_sec:.3f}],
  "tracks": [],
  "overall_confidence": 0.0,
  "needs_review": false,
  "notes": ["per-cut SNAP decisions"],
  "refine_decisions": [
    {{"from_sec": 40.0, "to_sec": 46.5, "reason": "after applause into banter"}}
  ]
}}

Rules:
- cuts_sec MUST begin with 0.0 and end with duration_sec (never omit endpoints).
- You may move mid cuts earlier/later within the clip window.
- Prefer the start of new material (count-in, first note of next song, banter onset).
- If the proposed cut is already correct, keep it (to_sec == from_sec).
- tracks may be an empty array; cuts_sec is required.
"""


def gap_fill_listen_prompt(
    *,
    show_id: str,
    duration_sec: float,
    existing_cuts_sec: list[float],
    windows: list[dict[str, Any]],
) -> str:
    """Prompt: INSERT missing track boundaries inside overlong segments."""
    win_lines = "\n".join(
        f"- probe {float(w['center_sec']):.3f}s "
        f"(clip covers {float(w['start_sec']):.3f}–{float(w['end_sec']):.3f}s)"
        for w in windows
    )
    return f"""You already have a partial tracking plan for a live show. Some segments
are suspiciously long — listen for *missed* track boundaries and INSERT them.

Show id: {show_id}
Master duration: {duration_sec:.3f}s
Existing cuts (including endpoints): {json.dumps(existing_cuts_sec)}

Etree convention: song ends, stage banter, tuning, and song intros are separate
tracks. Do not leave two songs (or song+banter) glued together.

You get short clips at probe centers inside long segments:
{win_lines}

For each probe: INSERT a cut near the probe if you hear a real track change
(applause into banter/new song, count-in, clear song boundary). REJECT if the
clip is continuous music with no track change.

Return ONLY JSON:
{{
  "schema_version": "1.0.0",
  "show_id": "{show_id}",
  "duration_sec": {duration_sec:.3f},
  "cuts_sec": [0.0, ...existing..., ...new inserts..., {duration_sec:.3f}],
  "tracks": [],
  "overall_confidence": 0.0,
  "needs_review": false,
  "notes": ["INSERT@t or REJECT@t decisions"],
  "insert_decisions": [
    {{"probe_sec": 687.0, "insert_sec": 690.5, "action": "INSERT", "reason": "applause into banter"}}
  ]
}}

Rules:
- cuts_sec MUST begin with 0.0 and end with duration_sec.
- Keep all existing cuts unless clearly wrong; ADD inserts for missed boundaries.
- Prefer insert_sec at the start of new material inside the clip.
- tracks may be empty; cuts_sec is required.
"""
