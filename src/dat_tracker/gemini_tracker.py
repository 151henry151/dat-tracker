"""Gemini audio listening client for sparse tracking decisions."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from dat_tracker.listen_clips import (
    add_gap_probe_centers,
    build_listen_windows,
    extract_audio_clip,
    load_dotenv_file,
    parse_model_json,
    tracking_listen_prompt,
)
from dat_tracker.tracking_plan import ensure_plan_tracks, validate_tracking_plan


def resolve_gemini_api_key(*, project_root: Path | None = None) -> str:
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if key:
        return key
    root = project_root or Path.cwd()
    vals = load_dotenv_file(root / ".env")
    key = vals.get("GEMINI_API_KEY") or vals.get("GOOGLE_API_KEY") or ""
    if not key:
        raise RuntimeError(
            "Set GEMINI_API_KEY in the environment or in a gitignored .env file"
        )
    return key


def resolve_gemini_model(*, project_root: Path | None = None) -> str:
    model = os.environ.get("DAT_TRACKER_LLM_MODEL")
    if model:
        return model
    root = project_root or Path.cwd()
    vals = load_dotenv_file(root / ".env")
    return vals.get("DAT_TRACKER_LLM_MODEL") or "gemini-3.6-flash"


def request_tracking_plan_from_clips(
    *,
    source_audio: Path,
    show_id: str,
    source_path: str,
    duration_sec: float,
    candidate_cuts_sec: list[float],
    work_dir: Path,
    half_window_sec: float = 8.0,
    probe_centers_sec: list[float] | None = None,
    api_key: str | None = None,
    model: str | None = None,
    project_root: Path | None = None,
    max_retries: int = 5,
) -> dict[str, Any]:
    """Extract sparse clips, ask Gemini to listen, validate tracking-plan JSON."""
    import time

    from google import genai
    from google.genai import types
    from google.genai.errors import ClientError, ServerError

    root = project_root or Path.cwd()
    key = api_key or resolve_gemini_api_key(project_root=root)
    model_name = model or resolve_gemini_model(project_root=root)

    listen_centers = sorted(
        {
            float(c)
            for c in [
                *candidate_cuts_sec,
                *(probe_centers_sec or []),
            ]
        }
    )
    windows = build_listen_windows(
        listen_centers,
        duration_sec=duration_sec,
        half_window_sec=half_window_sec,
        skip_endpoints=True,
        probe_centers_sec=probe_centers_sec,
    )
    if not windows:
        raise RuntimeError("No mid-show listen windows from candidates")

    work_dir.mkdir(parents=True, exist_ok=True)
    clip_paths: list[tuple[dict[str, Any], Path]] = []
    for i, win in enumerate(windows):
        dest = work_dir / (
            f"listen_{i:02d}_{win['role']}_{float(win['center_sec']):.1f}s.flac"
        )
        extract_audio_clip(
            source_audio,
            dest,
            start_sec=float(win["start_sec"]),
            end_sec=float(win["end_sec"]),
        )
        clip_paths.append((win, dest))

    prompt = tracking_listen_prompt(
        show_id=show_id,
        duration_sec=duration_sec,
        candidate_cuts_sec=candidate_cuts_sec,
        windows=windows,
    )

    client = genai.Client(api_key=key)
    parts: list[Any] = [types.Part.from_text(text=prompt)]
    for win, path in clip_paths:
        label = (
            f"\nAudio clip role={win['role']}: master center "
            f"{float(win['center_sec']):.3f}s "
            f"({float(win['start_sec']):.3f}–{float(win['end_sec']):.3f}s)\n"
        )
        parts.append(types.Part.from_text(text=label))
        parts.append(
            types.Part.from_bytes(
                data=path.read_bytes(),
                mime_type="audio/flac",
            )
        )

    last_error: Exception | None = None
    for attempt in range(max_retries):
        text = ""
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=[
                    types.Content(
                        role="user",
                        parts=parts,
                    )
                ],
                config=types.GenerateContentConfig(
                    temperature=0.2,
                    response_mime_type="application/json",
                    max_output_tokens=16384,
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(
                        disable=True
                    ),
                ),
            )
            text = _response_text(response)
            if not text.strip():
                raise ValueError("Empty Gemini response text")
            plan = parse_model_json(text)
            plan["show_id"] = show_id
            plan["source_path"] = source_path
            plan["schema_version"] = plan.get("schema_version") or "1.0.0"
            plan["duration_sec"] = float(duration_sec)
            if "notes" not in plan:
                plan["notes"] = []
            if "needs_review" not in plan:
                plan["needs_review"] = False
            if "overall_confidence" not in plan:
                plan["overall_confidence"] = 0.5
            plan = ensure_plan_tracks(plan)
            validate_tracking_plan(plan)
            return plan
        except (ServerError, ClientError) as exc:
            last_error = exc
            if attempt + 1 >= max_retries:
                raise
            status = getattr(exc, "code", None) or getattr(exc, "status_code", None)
            if status == 429:
                time.sleep(min(60.0, 15.0 * (attempt + 1)))
            else:
                time.sleep(2 ** attempt)
        except (json.JSONDecodeError, ValueError, TypeError) as exc:
            last_error = exc
            bad = work_dir / f"bad_listen_response_{attempt}.txt"
            bad.write_text(text or repr(exc), encoding="utf-8")
            if attempt + 1 >= max_retries:
                raise
            time.sleep(2 ** attempt)
    assert last_error is not None
    raise last_error


def _response_text(response: Any) -> str:
    text = getattr(response, "text", None) or ""
    if text:
        return text
    chunks: list[str] = []
    for cand in getattr(response, "candidates", None) or []:
        content = getattr(cand, "content", None)
        for part in getattr(content, "parts", None) or []:
            t = getattr(part, "text", None)
            if t:
                chunks.append(t)
    return "\n".join(chunks)


def coerce_refine_decision_times(
    decision: dict[str, Any],
) -> tuple[float, float] | None:
    """Parse refine from/to seconds; return None when Gemini omits/nulls them."""
    if "from_sec" not in decision and "to_sec" not in decision:
        return None
    raw_from = decision.get("from_sec", decision.get("to_sec"))
    raw_to = decision.get("to_sec", decision.get("from_sec"))
    if raw_from is None or raw_to is None:
        return None
    try:
        return float(raw_from), float(raw_to)
    except (TypeError, ValueError):
        return None


def _generate_content_with_retries(
    *,
    client: Any,
    model_name: str,
    parts: list[Any],
    max_retries: int,
) -> Any:
    import time

    import httpx
    from google.genai import types
    from google.genai.errors import ClientError, ServerError

    last_error: Exception | None = None
    for attempt in range(max_retries):
        try:
            return client.models.generate_content(
                model=model_name,
                contents=[types.Content(role="user", parts=parts)],
                config=types.GenerateContentConfig(
                    temperature=0.2,
                    response_mime_type="application/json",
                    max_output_tokens=16384,
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(
                        disable=True
                    ),
                ),
            )
        except (ServerError, ClientError) as exc:
            last_error = exc
            if attempt + 1 >= max_retries:
                raise
            status = getattr(exc, "code", None) or getattr(exc, "status_code", None)
            if status == 429:
                time.sleep(min(60.0, 15.0 * (attempt + 1)))
            else:
                time.sleep(2**attempt)
        except (httpx.HTTPError, OSError, TimeoutError) as exc:
            # Transient TLS / connection drops (e.g. SSLV3_ALERT_BAD_RECORD_MAC).
            last_error = exc
            if attempt + 1 >= max_retries:
                raise
            time.sleep(min(30.0, 2**attempt))
    assert last_error is not None
    raise last_error


def refine_tracking_plan_cuts(
    plan: dict[str, Any],
    *,
    source_audio: Path,
    work_dir: Path,
    half_window_sec: float = 20.0,
    api_key: str | None = None,
    model: str | None = None,
    project_root: Path | None = None,
    max_retries: int = 5,
) -> dict[str, Any]:
    """Second listen pass: snap mid cuts to where the next track begins."""
    from google import genai
    from google.genai import types

    from dat_tracker.refine_cuts import (
        ensure_endpoint_cuts,
        rebuild_tracks_from_cuts,
        refine_listen_prompt,
    )

    root = project_root or Path.cwd()
    key = api_key or resolve_gemini_api_key(project_root=root)
    model_name = model or resolve_gemini_model(project_root=root)
    duration_sec = float(plan["duration_sec"])
    proposed = [float(c) for c in plan.get("cuts_sec") or []]
    windows = build_listen_windows(
        proposed,
        duration_sec=duration_sec,
        half_window_sec=half_window_sec,
        skip_endpoints=True,
    )
    if not windows:
        return plan

    work_dir.mkdir(parents=True, exist_ok=True)
    clip_paths: list[tuple[dict[str, Any], Path]] = []
    for i, win in enumerate(windows):
        dest = work_dir / f"refine_{i:02d}_{float(win['center_sec']):.1f}s.flac"
        extract_audio_clip(
            source_audio,
            dest,
            start_sec=float(win["start_sec"]),
            end_sec=float(win["end_sec"]),
        )
        clip_paths.append((win, dest))

    prompt = refine_listen_prompt(
        show_id=str(plan["show_id"]),
        duration_sec=duration_sec,
        proposed_cuts_sec=proposed,
        windows=windows,
    )
    client = genai.Client(api_key=key)
    parts: list[Any] = [types.Part.from_text(text=prompt)]
    for win, path in clip_paths:
        label = (
            f"\nRefine clip around proposed cut {float(win['center_sec']):.3f}s "
            f"({float(win['start_sec']):.3f}–{float(win['end_sec']):.3f}s)\n"
        )
        parts.append(types.Part.from_text(text=label))
        parts.append(
            types.Part.from_bytes(data=path.read_bytes(), mime_type="audio/flac")
        )

    response = _generate_content_with_retries(
        client=client,
        model_name=model_name,
        parts=parts,
        max_retries=max_retries,
    )
    raw = parse_model_json(_response_text(response))
    new_cuts = [float(c) for c in raw.get("cuts_sec") or []]
    if len(new_cuts) < 2:
        # Fall back to refine_decisions map if cuts_sec omitted.
        decisions = {}
        for d in raw.get("refine_decisions") or []:
            parsed = coerce_refine_decision_times(d)
            if parsed is None:
                continue
            frm, to = parsed
            decisions[frm] = to
        new_cuts = [decisions.get(c, c) for c in proposed]

    evidence: dict[float, list[str]] = {}
    for decision in raw.get("refine_decisions") or []:
        parsed = coerce_refine_decision_times(decision)
        if parsed is None:
            continue
        frm, to_sec = parsed
        reason = str(decision.get("reason") or "")
        evidence.setdefault(to_sec, []).append(f"REFINE {frm}->{to_sec}: {reason}")

    # Refine responses sometimes omit 0 / duration; restore before rebuild.
    new_cuts = ensure_endpoint_cuts(new_cuts, duration_sec=duration_sec)

    refined = rebuild_tracks_from_cuts(
        plan,
        new_cuts,
        evidence_by_cut=evidence,
        note="Refined cut times toward new-track starts (second listen pass).",
    )
    refined["show_id"] = plan["show_id"]
    refined["source_path"] = plan.get("source_path")
    refined["schema_version"] = "1.0.0"
    refined["duration_sec"] = duration_sec
    refined["overall_confidence"] = float(
        raw.get("overall_confidence") or plan.get("overall_confidence") or 0.5
    )
    refined["needs_review"] = bool(
        raw.get("needs_review", plan.get("needs_review", False))
    )
    validate_tracking_plan(refined)
    return refined


def speech_anchor_cuts_with_probes(
    segments: list[dict[str, Any]],
    *,
    duration_sec: float,
    max_gap_sec: float = 240.0,
    probe_step_sec: float = 90.0,
    sparse_mid_anchor_threshold: int = 3,
    sparse_probe_step_sec: float = 60.0,
    energy_cuts: list[float] | None = None,
    silence_cuts: list[float] | None = None,
) -> tuple[list[float], list[float]]:
    """Speech-island starts as anchors; gap probes for long music spans.

    Also folds in onsets of overlong Whisper spans (common song-length
    hallucinations). When mid-show anchors are sparse, tighten probe spacing.
    Optional energy peaks and silence ends fill gaps that lack speech.

    Returns (anchor_cuts including endpoints, probe_centers only).
    """
    from dat_tracker.speech import (
        cuts_from_speech_islands,
        filter_plausible_speech_segments,
        long_segment_onset_candidates,
        merge_speech_islands,
    )

    islands = merge_speech_islands(
        filter_plausible_speech_segments(segments, max_seg_sec=20.0)
    )
    anchors = cuts_from_speech_islands(islands, duration_sec=duration_sec)
    for onset in long_segment_onset_candidates(segments, min_seg_sec=20.0):
        # Skip onsets that are just the tail of an already-kept banter island.
        if not any(abs(onset - a) <= 15.0 for a in anchors):
            anchors.append(onset)
    anchors = sorted(anchors)

    mid_anchors = [a for a in anchors if 0.05 < a < duration_sec - 0.05]
    step = probe_step_sec
    if len(mid_anchors) < sparse_mid_anchor_threshold:
        step = min(step, sparse_probe_step_sec)

    if energy_cuts:
        anchors = merge_energy_into_anchors(
            anchors=anchors,
            energy_cuts=energy_cuts,
            min_gap_sec=90.0,
            near_anchor_sec=30.0,
        )
    if silence_cuts:
        anchors = merge_energy_into_anchors(
            anchors=anchors,
            energy_cuts=silence_cuts,
            min_gap_sec=90.0,
            near_anchor_sec=30.0,
        )

    with_probes = add_gap_probe_centers(
        anchors,
        duration_sec=duration_sec,
        max_gap_sec=max_gap_sec,
        probe_step_sec=step,
    )
    probes = [
        c
        for c in with_probes
        if not any(abs(c - a) <= 0.05 for a in anchors)
    ]
    if energy_cuts:
        probes = merge_energy_into_probes(
            anchors=anchors,
            existing_probes=probes,
            energy_cuts=energy_cuts,
            min_gap_sec=max_gap_sec,
        )
    return anchors, probes


def merge_energy_into_anchors(
    *,
    anchors: list[float],
    energy_cuts: list[float],
    min_gap_sec: float = 90.0,
    near_anchor_sec: float = 30.0,
    edge_pad_sec: float = 20.0,
) -> list[float]:
    """Promote energy novelty peaks in medium speech gaps to listen anchors.

    Speech-free song transitions often lack Whisper islands; energy peaks in
    those gaps are stronger candidate cut centers than evenly spaced probes.
    """
    ordered = sorted(float(a) for a in anchors)
    added: list[float] = []
    for left, right in zip(ordered, ordered[1:], strict=False):
        if right - left <= min_gap_sec:
            continue
        for peak in energy_cuts:
            p = float(peak)
            if p <= left + edge_pad_sec or p >= right - edge_pad_sec:
                continue
            if any(abs(p - a) <= near_anchor_sec for a in (*ordered, *added)):
                continue
            added.append(p)
    return sorted({*ordered, *added})


def merge_energy_into_probes(
    *,
    anchors: list[float],
    existing_probes: list[float],
    energy_cuts: list[float],
    min_gap_sec: float = 240.0,
    edge_pad_sec: float = 20.0,
) -> list[float]:
    """Add energy novelty peaks inside long anchor gaps as extra listen probes."""
    ordered_anchors = sorted(float(a) for a in anchors)
    probes = list(existing_probes)
    for left, right in zip(ordered_anchors, ordered_anchors[1:], strict=False):
        if right - left <= min_gap_sec:
            continue
        for peak in energy_cuts:
            p = float(peak)
            if p <= left + edge_pad_sec or p >= right - edge_pad_sec:
                continue
            if any(abs(p - a) <= 5.0 for a in ordered_anchors):
                continue
            if any(abs(p - q) <= 5.0 for q in probes):
                continue
            probes.append(p)
    return sorted(probes)
