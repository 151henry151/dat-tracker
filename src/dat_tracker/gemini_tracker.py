"""Gemini audio listening client for sparse tracking decisions."""

from __future__ import annotations

import os
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
from dat_tracker.tracking_plan import validate_tracking_plan


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
) -> dict[str, Any]:
    """Extract sparse clips, ask Gemini to listen, validate tracking-plan JSON."""
    from google import genai
    from google.genai import types

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
            automatic_function_calling=types.AutomaticFunctionCallingConfig(
                disable=True
            ),
        ),
    )
    text = getattr(response, "text", None) or ""
    if not text and getattr(response, "candidates", None):
        chunks: list[str] = []
        for cand in response.candidates or []:
            content = getattr(cand, "content", None)
            for part in getattr(content, "parts", None) or []:
                t = getattr(part, "text", None)
                if t:
                    chunks.append(t)
        text = "\n".join(chunks)

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
    validate_tracking_plan(plan)
    return plan


def speech_anchor_cuts_with_probes(
    segments: list[dict[str, Any]],
    *,
    duration_sec: float,
    max_gap_sec: float = 240.0,
    probe_step_sec: float = 90.0,
) -> tuple[list[float], list[float]]:
    """Speech-island starts as anchors; gap probes for long music spans.

    Returns (anchor_cuts including endpoints, probe_centers only).
    """
    from dat_tracker.speech import (
        cuts_from_speech_islands,
        filter_plausible_speech_segments,
        merge_speech_islands,
    )

    islands = merge_speech_islands(
        filter_plausible_speech_segments(segments, max_seg_sec=20.0)
    )
    anchors = cuts_from_speech_islands(islands, duration_sec=duration_sec)
    with_probes = add_gap_probe_centers(
        anchors,
        duration_sec=duration_sec,
        max_gap_sec=max_gap_sec,
        probe_step_sec=probe_step_sec,
    )
    probes = [
        c
        for c in with_probes
        if not any(abs(c - a) <= 0.05 for a in anchors)
    ]
    return anchors, probes
