"""Propose track boundaries from ffmpeg silencedetect output."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from dat_tracker.ffmpeg_tools import ffmpeg_bin

SILENCE_START_RE = re.compile(r"silence_start:\s*(?P<t>-?\d+(?:\.\d+)?)")
SILENCE_END_RE = re.compile(r"silence_end:\s*(?P<t>-?\d+(?:\.\d+)?)")


def parse_silencedetect_lines(lines: list[str]) -> list[tuple[float, float]]:
    """Parse paired silence_start / silence_end regions from ffmpeg stderr lines."""
    regions: list[tuple[float, float]] = []
    start: float | None = None
    for line in lines:
        start_match = SILENCE_START_RE.search(line)
        if start_match:
            start = float(start_match.group("t"))
            continue
        end_match = SILENCE_END_RE.search(line)
        if end_match and start is not None:
            end = float(end_match.group("t"))
            if end >= start:
                regions.append((start, end))
            start = None
    return regions


def silence_midpoints(regions: list[tuple[float, float]]) -> list[float]:
    return [(start + end) / 2.0 for start, end in regions]


def silence_end_candidates(
    regions: list[tuple[float, float]],
    *,
    min_silence_sec: float = 0.8,
) -> list[float]:
    """Silence *ends* as cut candidates (start of next audible material)."""
    return sorted(
        float(end)
        for start, end in regions
        if (end - start) >= min_silence_sec
    )


def propose_cuts_from_silences(
    *,
    silence_regions: list[tuple[float, float]],
    duration_sec: float,
    min_silence_sec: float = 1.0,
    pad_sec: float = 1.0,
) -> list[float]:
    """Build cut list [0, …midpoints…, duration] from long-enough interior silences."""
    cuts = [0.0]
    for start, end in silence_regions:
        if (end - start) < min_silence_sec:
            continue
        mid = (start + end) / 2.0
        if mid < pad_sec or mid > (duration_sec - pad_sec):
            continue
        if cuts and abs(mid - cuts[-1]) < 0.05:
            continue
        cuts.append(mid)
    if duration_sec > 0 and (not cuts or abs(cuts[-1] - duration_sec) > 0.05):
        cuts.append(float(duration_sec))
    return cuts


def run_silencedetect(
    path: Path,
    *,
    noise_db: float = -40.0,
    min_silence_sec: float = 0.8,
) -> list[tuple[float, float]]:
    """Run ffmpeg silencedetect and return silence regions in seconds."""
    filter_arg = f"silencedetect=noise={noise_db}dB:d={min_silence_sec}"
    proc = subprocess.run(
        [
            ffmpeg_bin(),
            "-hide_banner",
            "-nostats",
            "-i",
            str(path),
            "-af",
            filter_arg,
            "-f",
            "null",
            "-",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    # silencedetect logs go to stderr; ffmpeg may exit 0 even with detections.
    lines = (proc.stderr or "").splitlines()
    return parse_silencedetect_lines(lines)
