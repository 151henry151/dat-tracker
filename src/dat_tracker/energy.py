"""Energy / novelty features for candidate track boundaries."""

from __future__ import annotations

import math
import struct
import subprocess
from pathlib import Path


def frame_rms_from_pcm(pcm: bytes, *, hop: int = 2000) -> list[float]:
    """RMS per hop of little-endian int16 mono PCM."""
    if not pcm:
        return []
    n_samples = len(pcm) // 2
    samples = struct.unpack("<" + "h" * n_samples, pcm[: n_samples * 2])
    frames: list[float] = []
    for i in range(0, n_samples, hop):
        chunk = samples[i : i + hop]
        if not chunk:
            break
        mean_sq = sum(s * s for s in chunk) / len(chunk)
        frames.append(math.sqrt(mean_sq))
    return frames


def novelty_from_rms(rms: list[float]) -> list[float]:
    """Absolute first difference of RMS (onset / drop novelty)."""
    if not rms:
        return []
    out = [0.0]
    for prev, cur in zip(rms, rms[1:], strict=False):
        out.append(abs(cur - prev))
    return out


def peaks_from_novelty(
    novelty: list[float],
    *,
    threshold: float,
    min_separation: int,
) -> list[int]:
    """Local maxima above threshold with a refractory gap in frames."""
    peaks: list[int] = []
    last = -10**9
    n = len(novelty)
    for i, value in enumerate(novelty):
        if value < threshold:
            continue
        left = novelty[i - 1] if i > 0 else -1.0
        right = novelty[i + 1] if i + 1 < n else -1.0
        if value < left or value < right:
            continue
        if i - last < min_separation:
            # Keep the stronger peak inside the refractory window.
            if peaks and value > novelty[peaks[-1]]:
                peaks[-1] = i
                last = i
            continue
        peaks.append(i)
        last = i
    return peaks


def propose_cuts_from_rms(
    rms: list[float],
    *,
    sample_rate: int,
    hop: int,
    novelty_threshold: float,
    min_separation_sec: float,
) -> list[float]:
    """Convert RMS frames to cut times [0, …peaks…, duration]."""
    if not rms:
        return [0.0]
    novelty = novelty_from_rms(rms)
    min_sep_frames = max(1, int(min_separation_sec * sample_rate / hop))
    peak_idxs = peaks_from_novelty(
        novelty, threshold=novelty_threshold, min_separation=min_sep_frames
    )
    cuts = [0.0]
    for idx in peak_idxs:
        t = idx * hop / float(sample_rate)
        if t > 0.05:
            cuts.append(t)
    duration = len(rms) * hop / float(sample_rate)
    if abs(cuts[-1] - duration) > 0.05:
        cuts.append(duration)
    return cuts


def extract_mono_pcm(
    path: Path,
    *,
    sample_rate: int = 2000,
    start_sec: float = 0.0,
    duration_sec: float | None = None,
) -> bytes:
    """Decode mono s16le PCM via ffmpeg for analysis."""
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
    return subprocess.run(cmd, check=True, capture_output=True).stdout


def propose_cuts_from_audio(
    path: Path,
    *,
    sample_rate: int = 2000,
    hop: int = 2000,
    novelty_threshold: float | None = None,
    min_separation_sec: float = 8.0,
) -> list[float]:
    """End-to-end energy novelty proposals for one audio file."""
    pcm = extract_mono_pcm(path, sample_rate=sample_rate)
    rms = frame_rms_from_pcm(pcm, hop=hop)
    if not rms:
        return [0.0]
    if novelty_threshold is None:
        # Adaptive: peak if jump exceeds median novelty * k
        nov = novelty_from_rms(rms)
        positive = [v for v in nov if v > 0]
        median = sorted(positive)[len(positive) // 2] if positive else 1.0
        novelty_threshold = max(median * 4.0, 50.0)
    return propose_cuts_from_rms(
        rms,
        sample_rate=sample_rate,
        hop=hop,
        novelty_threshold=novelty_threshold,
        min_separation_sec=min_separation_sec,
    )
