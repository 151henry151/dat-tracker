"""Speech-segment helpers for banter-aware boundary candidates."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any


def parse_whisper_segments(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize whisper / faster-whisper JSON segments."""
    segments = payload.get("segments") or []
    out: list[dict[str, Any]] = []
    for seg in segments:
        text = str(seg.get("text") or "").strip()
        out.append(
            {
                "start": float(seg["start"]),
                "end": float(seg["end"]),
                "text": text,
            }
        )
    return out


def cuts_from_speech_segments(
    segments: list[dict[str, Any]],
    *,
    duration_sec: float,
    min_seg_sec: float = 0.5,
) -> list[float]:
    """Turn speech islands into cut candidates at segment edges."""
    cuts = [0.0]
    for seg in segments:
        start = float(seg["start"])
        end = float(seg["end"])
        if end - start < min_seg_sec:
            continue
        for t in (start, end):
            if not cuts or abs(cuts[-1] - t) > 0.05:
                cuts.append(t)
    if duration_sec > 0 and abs(cuts[-1] - duration_sec) > 0.05:
        cuts.append(float(duration_sec))
    return cuts


def filter_plausible_speech_segments(
    segments: list[dict[str, Any]],
    *,
    max_seg_sec: float = 20.0,
) -> list[dict[str, Any]]:
    """Drop segments that are too long to be real banter (Whisper music spans)."""
    out: list[dict[str, Any]] = []
    for seg in segments:
        start = float(seg["start"])
        end = float(seg["end"])
        if end - start > max_seg_sec:
            continue
        out.append(seg)
    return out


def long_segment_onset_candidates(
    segments: list[dict[str, Any]],
    *,
    min_seg_sec: float = 20.0,
    min_start_sec: float = 0.5,
) -> list[float]:
    """Keep starts of overlong Whisper spans as weak boundary hints.

    Whisper often glues a whole song into one segment; the onset can still land
    near a real track change even though the text/end time are wrong.
    """
    onsets: list[float] = []
    for seg in segments:
        start = float(seg["start"])
        end = float(seg["end"])
        if start < min_start_sec:
            continue
        if end - start < min_seg_sec:
            continue
        onsets.append(start)
    return onsets


def merge_speech_islands(
    segments: list[dict[str, Any]],
    *,
    merge_gap_sec: float = 15.0,
) -> list[dict[str, Any]]:
    """Merge nearby speech segments into banter islands."""
    if not segments:
        return []
    ordered = sorted(segments, key=lambda s: float(s["start"]))
    islands: list[dict[str, Any]] = [
        {
            "start": float(ordered[0]["start"]),
            "end": float(ordered[0]["end"]),
            "text": str(ordered[0].get("text") or "").strip(),
        }
    ]
    for seg in ordered[1:]:
        start = float(seg["start"])
        end = float(seg["end"])
        text = str(seg.get("text") or "").strip()
        cur = islands[-1]
        if start - cur["end"] <= merge_gap_sec:
            cur["end"] = max(cur["end"], end)
            if text:
                cur["text"] = f"{cur['text']} {text}".strip()
        else:
            islands.append({"start": start, "end": end, "text": text})
    return islands


def cuts_from_speech_islands(
    islands: list[dict[str, Any]],
    *,
    duration_sec: float,
    min_island_sec: float = 1.0,
) -> list[float]:
    """Prefer island starts as mid-show cuts (banter track openings)."""
    cuts = [0.0]
    for island in islands:
        start = float(island["start"])
        end = float(island["end"])
        if end - start < min_island_sec:
            continue
        if start > 0.05 and abs(cuts[-1] - start) > 0.05:
            cuts.append(start)
    if duration_sec > 0 and abs(cuts[-1] - duration_sec) > 0.05:
        cuts.append(float(duration_sec))
    return cuts


def snap_cuts_to_nearby(
    cuts: list[float],
    *,
    anchors: list[float],
    window_sec: float,
) -> list[float]:
    """Move each cut to the nearest anchor within window_sec, else keep it."""
    snapped: list[float] = []
    for cut in cuts:
        nearby = [a for a in anchors if abs(a - cut) <= window_sec]
        if nearby:
            snapped.append(min(nearby, key=lambda a: abs(a - cut)))
        else:
            snapped.append(float(cut))
    return snapped


def _dedupe_sorted(cuts: list[float], *, tol: float = 0.05) -> list[float]:
    if not cuts:
        return []
    ordered = sorted(float(c) for c in cuts)
    out = [ordered[0]]
    for cut in ordered[1:]:
        if cut - out[-1] > tol:
            out.append(cut)
    return out


def _sparse_fill_gap(
    *,
    gap_start: float,
    gap_end: float,
    energy_cuts: list[float],
    min_separation_sec: float,
    edge_pad_sec: float = 15.0,
) -> list[float]:
    """Pick energy peaks inside a long gap with refractory spacing."""
    candidates = [
        e
        for e in energy_cuts
        if gap_start + edge_pad_sec < e < gap_end - edge_pad_sec
    ]
    if not candidates:
        return []
    picked: list[float] = []
    last = gap_start
    for cut in candidates:
        if cut - last < min_separation_sec:
            continue
        if gap_end - cut < min_separation_sec:
            continue
        picked.append(cut)
        last = cut
    return picked


def propose_speech_prioritized_cuts(
    segments: list[dict[str, Any]],
    *,
    energy_cuts: list[float],
    duration_sec: float,
    max_seg_sec: float = 20.0,
    merge_gap_sec: float = 15.0,
    min_island_sec: float = 1.0,
    snap_window_sec: float = 8.0,
    max_gap_sec: float = 240.0,
    fill_min_separation_sec: float = 90.0,
) -> list[float]:
    """Speech-island starts first; snap to energy; fill long song gaps sparsely."""
    filtered = filter_plausible_speech_segments(segments, max_seg_sec=max_seg_sec)
    islands = merge_speech_islands(filtered, merge_gap_sec=merge_gap_sec)
    speech_cuts = cuts_from_speech_islands(
        islands, duration_sec=duration_sec, min_island_sec=min_island_sec
    )
    # Snap interior speech cuts (skip forced endpoints).
    interior = [c for c in speech_cuts if 0.05 < c < duration_sec - 0.05]
    snapped_interior = snap_cuts_to_nearby(
        interior, anchors=energy_cuts, window_sec=snap_window_sec
    )
    anchors = _dedupe_sorted([0.0, *snapped_interior, float(duration_sec)])

    fills: list[float] = []
    for left, right in zip(anchors, anchors[1:], strict=False):
        if right - left <= max_gap_sec:
            continue
        fills.extend(
            _sparse_fill_gap(
                gap_start=left,
                gap_end=right,
                energy_cuts=energy_cuts,
                min_separation_sec=fill_min_separation_sec,
            )
        )
    return _dedupe_sorted([*anchors, *fills])


def transcribe_faster_whisper(
    audio_path: Path,
    *,
    model_size: str = "base",
    language: str = "en",
    device: str = "cpu",
    compute_type: str = "int8",
) -> dict[str, Any]:
    """Transcribe with faster-whisper; return whisper-like JSON segments."""
    from faster_whisper import WhisperModel

    model = WhisperModel(model_size, device=device, compute_type=compute_type)
    segments_iter, _info = model.transcribe(
        str(audio_path), language=language, vad_filter=True
    )
    segments = [
        {
            "start": float(seg.start),
            "end": float(seg.end),
            "text": (seg.text or "").strip(),
        }
        for seg in segments_iter
    ]
    return {"segments": segments}


def transcribe_whisper_cli(
    audio_path: Path,
    *,
    model: str = "base",
    language: str = "en",
) -> dict[str, Any]:
    """Run `whisper` CLI if installed; return parsed JSON payload."""
    out_dir = audio_path.parent / ".whisper"
    out_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "whisper",
            str(audio_path),
            "--model",
            model,
            "--language",
            language,
            "--output_format",
            "json",
            "--output_dir",
            str(out_dir),
            "--verbose",
            "False",
        ],
        check=True,
    )
    json_path = out_dir / f"{audio_path.stem}.json"
    return json.loads(json_path.read_text())
