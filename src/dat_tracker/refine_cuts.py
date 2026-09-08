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
- Keep endpoints 0 and duration_sec.
- You may move mid cuts earlier/later within the clip window.
- Prefer the start of new material (count-in, first note of next song, banter onset).
- If the proposed cut is already correct, keep it (to_sec == from_sec).
- tracks may be an empty array; cuts_sec is required.
"""
