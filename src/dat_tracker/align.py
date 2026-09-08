"""Align a short ground-truth snippet inside a longer raw recording via energy."""

from __future__ import annotations

import math
import struct
import subprocess
from pathlib import Path


def pcm_energy(pcm: bytes, *, hop: int = 2000) -> list[float]:
    """Mean-square energy per hop of little-endian int16 mono PCM."""
    if not pcm:
        return []
    n_samples = len(pcm) // 2
    samples = struct.unpack("<" + "h" * n_samples, pcm[: n_samples * 2])
    energies: list[float] = []
    for i in range(0, n_samples, hop):
        chunk = samples[i : i + hop]
        if not chunk:
            break
        energies.append(sum(s * s for s in chunk) / len(chunk))
    return energies


def normalize_energy(values: list[float]) -> list[float]:
    """Mean-center and unit-normalize an energy contour."""
    if not values:
        return []
    mean = sum(values) / len(values)
    centered = [v - mean for v in values]
    norm = math.sqrt(sum(v * v for v in centered))
    if norm == 0.0:
        return [0.0 for _ in centered]
    return [v / norm for v in centered]


def sliding_energy_distance(
    haystack: list[float], needle: list[float]
) -> tuple[int, float]:
    """Return (best_start_index, L2 distance) for needle in haystack energies."""
    if not needle:
        raise ValueError("needle energy is empty")
    if len(haystack) < len(needle):
        raise ValueError("haystack shorter than needle")
    best_i = 0
    best_dist = float("inf")
    n = len(needle)
    for i in range(0, len(haystack) - n + 1):
        window = haystack[i : i + n]
        dist = math.sqrt(sum((a - b) ** 2 for a, b in zip(window, needle, strict=True)))
        if dist < best_dist:
            best_dist = dist
            best_i = i
    return best_i, best_dist


def best_offset_sec(
    haystack: list[float],
    needle: list[float],
    *,
    sample_rate: int,
    hop: int,
) -> tuple[float, float]:
    """Convert best energy-frame index into seconds."""
    idx, dist = sliding_energy_distance(haystack, needle)
    return idx * hop / float(sample_rate), dist


def extract_pcm_mono(
    path: Path,
    *,
    start_sec: float = 0.0,
    duration_sec: float | None = None,
    sample_rate: int = 2000,
) -> bytes:
    """Decode a mono s16le PCM snippet via ffmpeg."""
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        str(start_sec),
        "-i",
        str(path),
    ]
    if duration_sec is not None:
        cmd.extend(["-t", str(duration_sec)])
    cmd.extend(["-ac", "1", "-ar", str(sample_rate), "-f", "s16le", "-"])
    proc = subprocess.run(cmd, check=True, capture_output=True)
    return proc.stdout


def align_snippet_in_raw(
    raw_path: Path,
    snippet_path: Path,
    *,
    snippet_duration_sec: float = 45.0,
    sample_rate: int = 1000,
    hop: int = 1000,
) -> tuple[float, float]:
    """Find where snippet_path's opening energy best matches inside raw_path."""
    needle_pcm = extract_pcm_mono(
        snippet_path,
        start_sec=0.0,
        duration_sec=snippet_duration_sec,
        sample_rate=sample_rate,
    )
    hay_pcm = extract_pcm_mono(
        raw_path, start_sec=0.0, duration_sec=None, sample_rate=sample_rate
    )
    needle = pcm_energy(needle_pcm, hop=hop)
    hay = pcm_energy(hay_pcm, hop=hop)
    return best_offset_sec(hay, needle, sample_rate=sample_rate, hop=hop)
