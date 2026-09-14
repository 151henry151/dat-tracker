"""Compare hypothesized track boundaries to ground-truth cut times."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

from dat_tracker.ffmpeg_tools import ffprobe_bin

TRACK_SET_RE = re.compile(r"_[sS](?P<set>\d+)t(?P<st>\d+)", re.IGNORECASE)
TRACK_DISC_RE = re.compile(r"d(?P<set>\d+)t(?P<st>\d+)", re.IGNORECASE)
TRACK_AFTER_DATE_RE = re.compile(
    r"(?:\d{4}-\d{2}-\d{2}|\d{6})t(?P<t>\d+)", re.IGNORECASE
)
TRACK_UNDERSCORE_RE = re.compile(r"_t(?P<t>\d+)", re.IGNORECASE)


def cuts_from_durations(durations_sec: list[float]) -> list[float]:
    """Return track start times plus the show end from consecutive durations."""
    cuts = [0.0]
    total = 0.0
    for duration in durations_sec:
        total += float(duration)
        cuts.append(total)
    return cuts


def _track_sort_key(path: Path) -> tuple[int, int]:
    stem = path.stem
    match = TRACK_SET_RE.search(stem)
    if match:
        return (int(match.group("set")), int(match.group("st")))
    match = TRACK_DISC_RE.search(stem)
    if match:
        return (int(match.group("set")), int(match.group("st")))
    match = TRACK_AFTER_DATE_RE.search(stem)
    if match:
        return (1, int(match.group("t")))
    match = TRACK_UNDERSCORE_RE.search(stem)
    if match:
        return (1, int(match.group("t")))
    return (10_000, 10_000)


def list_track_flacs(directory: Path) -> list[Path]:
    """List etree-style track FLACs in playback order."""
    flacs = [p for p in directory.iterdir() if p.suffix.lower() == ".flac"]
    return sorted(flacs, key=_track_sort_key)


def parse_ffprobe_duration(payload: dict[str, Any]) -> float:
    """Extract seconds from an ffprobe `-show_format` JSON object."""
    duration = payload.get("format", {}).get("duration")
    if duration is None:
        raise ValueError("ffprobe JSON missing format.duration")
    return float(duration)


def probe_duration_seconds(path: Path) -> float:
    """Return media duration in seconds via ffprobe."""
    proc = subprocess.run(
        [
            ffprobe_bin(),
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return parse_ffprobe_duration(json.loads(proc.stdout))


def reference_cuts_from_durations_map(durations: dict[Path, float]) -> list[float]:
    """Build reference cuts from a path→duration map using etree filename order."""
    ordered = sorted(durations.keys(), key=_track_sort_key)
    return cuts_from_durations([durations[p] for p in ordered])


def reference_cuts_from_ground_truth_dir(directory: Path) -> list[float]:
    """Probe Jon track FLACs in a ground-truth item dir and return cut times."""
    tracks = list_track_flacs(directory)
    if not tracks:
        raise FileNotFoundError(f"No track FLACs in {directory}")
    durations = {path: probe_duration_seconds(path) for path in tracks}
    return reference_cuts_from_durations_map(durations)


def boundary_f1(
    reference_cuts: list[float],
    hypothesis_cuts: list[float],
    *,
    tolerance_sec: float,
) -> dict[str, float | int]:
    """One-to-one greedy match of cuts within tolerance; return precision/recall/F1."""
    ref = sorted(float(x) for x in reference_cuts)
    hyp = sorted(float(x) for x in hypothesis_cuts)
    matched_ref: set[int] = set()
    matched_hyp: set[int] = set()
    for hi, h in enumerate(hyp):
        best_ri = None
        best_dist = None
        for ri, r in enumerate(ref):
            if ri in matched_ref:
                continue
            dist = abs(h - r)
            if dist <= tolerance_sec and (best_dist is None or dist < best_dist):
                best_dist = dist
                best_ri = ri
        if best_ri is not None:
            matched_ref.add(best_ri)
            matched_hyp.add(hi)

    matched = len(matched_ref)
    precision = matched / len(hyp) if hyp else 0.0
    recall = matched / len(ref) if ref else 0.0
    f1 = (
        0.0
        if precision + recall == 0.0
        else 2.0 * precision * recall / (precision + recall)
    )
    return {
        "matched": matched,
        "reference_count": len(ref),
        "hypothesis_count": len(hyp),
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def summarize_comparison(
    *,
    reference_cuts: list[float],
    hypothesis_cuts: list[float],
    tolerance_sec: float,
) -> dict[str, Any]:
    """Boundary F1 plus track-count delta (tracks ≈ cuts - 1)."""
    metrics = boundary_f1(
        reference_cuts, hypothesis_cuts, tolerance_sec=tolerance_sec
    )
    ref_tracks = max(0, len(reference_cuts) - 1)
    hyp_tracks = max(0, len(hypothesis_cuts) - 1)
    return {
        **metrics,
        "tolerance_sec": tolerance_sec,
        "reference_tracks": ref_tracks,
        "hypothesis_tracks": hyp_tracks,
        "track_count_delta": hyp_tracks - ref_tracks,
    }
