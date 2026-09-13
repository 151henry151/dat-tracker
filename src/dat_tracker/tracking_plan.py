"""Structured tracking plans for LLM (and heuristic dry-run) decisions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

TRACKING_PLAN_SCHEMA_PATH = (
    Path(__file__).resolve().parents[2] / "catalog" / "tracking_plan.schema.json"
)


def load_tracking_plan_schema() -> dict[str, Any]:
    return json.loads(TRACKING_PLAN_SCHEMA_PATH.read_text())


def validate_tracking_plan(plan: dict[str, Any]) -> None:
    """Raise jsonschema.ValidationError if plan is invalid."""
    Draft202012Validator(load_tracking_plan_schema()).validate(plan)


def ensure_plan_tracks(plan: dict[str, Any]) -> dict[str, Any]:
    """Fill tracks from cuts_sec when the model returns an empty tracks array."""
    if plan.get("tracks"):
        return plan
    from dat_tracker.refine_cuts import rebuild_tracks_from_cuts

    cuts = [float(c) for c in (plan.get("cuts_sec") or [])]
    return rebuild_tracks_from_cuts(
        plan,
        cuts,
        note="Materialized tracks from cuts_sec (model returned empty tracks).",
    )


def _overlap_sec(a0: float, a1: float, b0: float, b1: float) -> float:
    return max(0.0, min(a1, b1) - max(a0, b0))


def _label_track(
    *,
    start: float,
    end: float,
    index: int,
    speech_islands: list[dict[str, Any]],
    speech_cut_sec: set[float],
) -> tuple[str, float, list[str]]:
    duration = max(end - start, 1e-6)
    evidence: list[str] = []
    speech_overlap = sum(
        _overlap_sec(start, end, float(i["start"]), float(i["end"]))
        for i in speech_islands
    )
    speech_frac = speech_overlap / duration

    near_speech_cut = any(abs(start - s) <= 12.0 for s in speech_cut_sec)
    if near_speech_cut:
        evidence.append("speech_island")

    if index == 1 and duration <= 30.0 and speech_frac >= 0.3:
        return "intro", 0.75, evidence + ["short_opening_speech"]

    if speech_frac >= 0.35 and duration <= 90.0:
        return "banter", 0.8, evidence + [f"speech_frac={speech_frac:.2f}"]

    if near_speech_cut and speech_frac >= 0.05:
        # Song that opens on / after banter — keep as song, speech noted.
        return "song", 0.7, evidence + [f"speech_frac={speech_frac:.2f}"]

    if not near_speech_cut and duration >= 90.0:
        return "song", 0.55, evidence + ["energy_fill"]

    return "unknown", 0.4, evidence + ["weak_signal"]


def build_draft_tracking_plan(
    *,
    show_id: str,
    source_path: str,
    duration_sec: float,
    cuts_sec: list[float],
    speech_islands: list[dict[str, Any]] | None = None,
    speech_cut_sec: set[float] | None = None,
    review_confidence_below: float = 0.45,
) -> dict[str, Any]:
    """Heuristic draft plan from proposed cuts + ASR islands (no LLM call)."""
    islands = speech_islands or []
    speech_cuts = speech_cut_sec or set()
    ordered = sorted(float(c) for c in cuts_sec)
    if not ordered or ordered[0] > 0.05:
        ordered = [0.0, *ordered]
    if abs(ordered[-1] - duration_sec) > 0.05:
        ordered.append(float(duration_sec))

    tracks: list[dict[str, Any]] = []
    notes: list[str] = []
    for i, (start, end) in enumerate(zip(ordered, ordered[1:], strict=False), start=1):
        track_type, confidence, evidence = _label_track(
            start=start,
            end=end,
            index=i,
            speech_islands=islands,
            speech_cut_sec=speech_cuts,
        )
        tracks.append(
            {
                "index": i,
                "start_sec": start,
                "end_sec": end,
                "track_type": track_type,
                "title": None,
                "segue_into_next": False,
                "confidence": confidence,
                "evidence": evidence,
            }
        )

    if tracks:
        overall = sum(t["confidence"] for t in tracks) / len(tracks)
    else:
        overall = 0.0
    needs_review = overall < review_confidence_below or any(
        t["track_type"] == "unknown" for t in tracks
    )
    if needs_review:
        notes.append("Draft heuristic only; overall confidence or unknown tracks need LLM.")

    plan = {
        "schema_version": "1.1.0",
        "show_id": show_id,
        "source_path": source_path,
        "duration_sec": float(duration_sec),
        "cuts_sec": ordered,
        "tracks": tracks,
        "overall_confidence": round(overall, 3),
        "needs_review": needs_review,
        "notes": notes,
        "package": {
            "artist": None,
            "date": None,
            "venue": None,
            "city": None,
            "state": None,
            "source": None,
            "transfer": None,
            "transferer": None,
            "tracker": None,
            "collection_subjects": [],
            "set_label": None,
            "notes": None,
        },
        "review": {
            "status": "pending",
            "approved_at": None,
            "approved_by": None,
            "method": None,
        },
    }
    validate_tracking_plan(plan)
    return plan
