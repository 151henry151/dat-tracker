"""Peak-envelope waveform for TUI review (cross-platform Unicode render)."""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import numpy as np

# Vertical braille-ish blocks from quiet → loud (single-column).
_BLOCKS = " ▁▂▃▄▅▆▇█"


def _decode_mono_float32(audio_path: Path, *, sample_rate: int = 8000) -> np.ndarray:
    """Decode audio to mono float32 PCM via ffmpeg (no soundfile required at decode)."""
    with tempfile.NamedTemporaryFile(suffix=".f32", delete=False) as tmp:
        raw_path = Path(tmp.name)
    try:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(audio_path),
                "-ac",
                "1",
                "-ar",
                str(sample_rate),
                "-f",
                "f32le",
                str(raw_path),
            ],
            check=True,
            capture_output=True,
        )
        data = np.fromfile(raw_path, dtype="<f4")
    finally:
        raw_path.unlink(missing_ok=True)
    if data.size == 0:
        raise ValueError(f"empty decode for {audio_path}")
    return data


def compute_peak_envelope(
    audio_path: Path,
    *,
    bucket_count: int = 2000,
    sample_rate: int = 8000,
) -> dict[str, Any]:
    """Return peak envelope dict: peaks (0..1), duration_sec, sample_rate, bucket_count."""
    samples = _decode_mono_float32(Path(audio_path), sample_rate=sample_rate)
    duration_sec = float(samples.size) / float(sample_rate)
    bucket_count = max(1, int(bucket_count))
    # Split into buckets; take max abs per bucket.
    edges = np.linspace(0, samples.size, bucket_count + 1, dtype=int)
    peaks = np.zeros(bucket_count, dtype=np.float64)
    for i in range(bucket_count):
        chunk = samples[edges[i] : edges[i + 1]]
        if chunk.size:
            peaks[i] = float(np.max(np.abs(chunk)))
    peak_max = float(peaks.max()) if peaks.size else 1.0
    if peak_max > 0:
        peaks = peaks / peak_max
    return {
        "peaks": peaks.astype(np.float32),
        "duration_sec": duration_sec,
        "sample_rate": sample_rate,
        "bucket_count": bucket_count,
        "source": str(audio_path),
    }


def save_envelope(env: dict[str, Any], cache_path: Path) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        cache_path,
        peaks=np.asarray(env["peaks"], dtype=np.float32),
        duration_sec=np.float64(env["duration_sec"]),
        sample_rate=np.int32(env["sample_rate"]),
        bucket_count=np.int32(env["bucket_count"]),
    )
    meta = {"source": env.get("source")}
    cache_path.with_suffix(".json").write_text(json.dumps(meta) + "\n")


def load_envelope(cache_path: Path) -> dict[str, Any]:
    data = np.load(cache_path)
    meta_path = cache_path.with_suffix(".json")
    source = None
    if meta_path.is_file():
        source = json.loads(meta_path.read_text()).get("source")
    return {
        "peaks": data["peaks"],
        "duration_sec": float(data["duration_sec"]),
        "sample_rate": int(data["sample_rate"]),
        "bucket_count": int(data["bucket_count"]),
        "source": source,
    }


def load_or_build_envelope(
    audio_path: Path,
    *,
    cache_path: Path,
    bucket_count: int = 2000,
    sample_rate: int = 8000,
) -> dict[str, Any]:
    audio_path = Path(audio_path)
    cache_path = Path(cache_path)
    if cache_path.is_file():
        env = load_envelope(cache_path)
        if int(env["bucket_count"]) == int(bucket_count):
            return env
    env = compute_peak_envelope(
        audio_path, bucket_count=bucket_count, sample_rate=sample_rate
    )
    save_envelope(env, cache_path)
    return env


def marker_column(time_sec: float, *, duration_sec: float, width: int) -> int:
    if width <= 0 or duration_sec <= 0:
        return 0
    frac = max(0.0, min(1.0, float(time_sec) / float(duration_sec)))
    col = int(round(frac * (width - 1)))
    return max(0, min(width - 1, col))


def column_to_time_sec(col: int, *, duration_sec: float, width: int) -> float:
    """Inverse of marker_column (approximate center of the column)."""
    width = max(1, int(width))
    duration_sec = max(0.0, float(duration_sec))
    if width <= 1:
        return 0.0
    col = max(0, min(width - 1, int(col)))
    return (col / (width - 1)) * duration_sec


def nearest_cut_index_at_column(
    cuts_sec: list[float],
    *,
    click_col: int,
    width: int,
    duration_sec: float,
    max_col_distance: int = 2,
) -> int | None:
    """Return cut index whose marker column is within ``max_col_distance`` of click."""
    if not cuts_sec or width <= 0 or duration_sec <= 0:
        return None
    best_i: int | None = None
    best_dist: int | None = None
    for i, t in enumerate(cuts_sec):
        col = marker_column(float(t), duration_sec=duration_sec, width=width)
        dist = abs(col - int(click_col))
        if dist > max_col_distance:
            continue
        if best_dist is None or dist < best_dist:
            best_dist = dist
            best_i = i
    return best_i


def render_envelope_line(
    peaks: list[float] | np.ndarray,
    *,
    width: int,
    markers_sec: list[float] | None = None,
    duration_sec: float | None = None,
    playhead_sec: float | None = None,
) -> str:
    """Render one waveform line of `width` characters with optional cut markers."""
    width = max(1, int(width))
    arr = np.asarray(peaks, dtype=float)
    if arr.size == 0:
        base = [" "] * width
    else:
        if arr.size != width:
            xs = np.linspace(0, arr.size - 1, width)
            sampled = np.interp(xs, np.arange(arr.size), arr)
        else:
            sampled = arr
        base = []
        for value in sampled:
            level = int(round(max(0.0, min(1.0, float(value))) * (len(_BLOCKS) - 1)))
            base.append(_BLOCKS[level])

    chars = list(base)
    dur = float(duration_sec) if duration_sec is not None else float(len(peaks) or 1)
    for t in markers_sec or []:
        col = marker_column(float(t), duration_sec=dur, width=width)
        chars[col] = "|"
    if playhead_sec is not None:
        col = marker_column(float(playhead_sec), duration_sec=dur, width=width)
        chars[col] = "▶"
    return "".join(chars)


def _resample_peaks(peaks: list[float] | np.ndarray, width: int) -> np.ndarray:
    """Downsample with max-pooling (preserves spikes); upsample with interp."""
    arr = np.asarray(peaks, dtype=float)
    width = max(1, int(width))
    if arr.size == 0:
        return np.zeros(width, dtype=float)
    if arr.size == width:
        return arr
    if arr.size < width:
        xs = np.linspace(0, arr.size - 1, width)
        return np.interp(xs, np.arange(arr.size), arr)
    edges = np.linspace(0, arr.size, width + 1, dtype=int)
    out = np.zeros(width, dtype=float)
    for i in range(width):
        chunk = arr[edges[i] : edges[i + 1]]
        if chunk.size:
            out[i] = float(np.max(chunk))
    return out


def _format_mmss(sec: float) -> str:
    sec = max(0.0, float(sec))
    m = int(sec // 60)
    s = int(sec % 60)
    return f"{m}:{s:02d}"


def render_time_ruler(*, duration_sec: float, width: int) -> str:
    """Return a width-character ruler with start/mid/end time labels."""
    width = max(8, int(width))
    duration_sec = max(0.01, float(duration_sec))
    chars = ["·"] * width
    labels = [
        (0, _format_mmss(0.0)),
        (width // 2, _format_mmss(duration_sec / 2.0)),
        (width - 1, _format_mmss(duration_sec)),
    ]
    for anchor, label in labels:
        start = max(0, min(width - len(label), anchor - len(label) // 2))
        if anchor == width - 1:
            start = width - len(label)
        if anchor == 0:
            start = 0
        for i, ch in enumerate(label):
            chars[start + i] = ch
    return "".join(chars)


def render_envelope_panel(
    peaks: list[float] | np.ndarray,
    *,
    width: int,
    height: int,
    markers_sec: list[float] | None = None,
    duration_sec: float | None = None,
    playhead_sec: float | None = None,
    selected_marker_sec: float | None = None,
    viewport_sec: tuple[float, float] | None = None,
    return_grid: bool = False,
    return_meta: bool = False,
):
    """Render a multi-row amplitude silhouette with cut/playhead overlays.

    Uses max-pooled columns and half-block characters (``▄``) for smoother
    vertical resolution than solid ``█`` stair-steps.

    Returns a plain multiline string by default. With ``return_grid=True``,
    returns a list of row character lists (and optionally meta when
    ``return_meta=True``).
    """
    width = max(1, int(width))
    height = max(1, int(height))
    sampled = _resample_peaks(peaks, width)
    # Sqrt so quiet gaps read as gaps instead of a flat wall.
    amp = np.sqrt(np.clip(sampled, 0.0, 1.0))
    # Two half-rows per text row → smoother tops.
    half_levels = amp * (height * 2)
    half_levels = np.clip(np.round(half_levels), 0, height * 2).astype(int)

    grid = [[" " for _ in range(width)] for _ in range(height)]
    for x in range(width):
        halves = int(half_levels[x])
        full = halves // 2
        partial = halves % 2
        for y in range(height - full, height):
            grid[y][x] = "█"
        if partial and full < height:
            top = height - full - 1
            grid[top][x] = "▄"

    dur = float(duration_sec) if duration_sec is not None else float(len(peaks) or 1)
    viewport_cols: tuple[int, int] | None = None
    if viewport_sec is not None:
        v0 = marker_column(float(viewport_sec[0]), duration_sec=dur, width=width)
        v1 = marker_column(float(viewport_sec[1]), duration_sec=dur, width=width)
        if v1 < v0:
            v0, v1 = v1, v0
        viewport_cols = (v0, v1)
        for x in range(v0, v1 + 1):
            for y in range(height):
                if grid[y][x] == " ":
                    grid[y][x] = "·"

    for t in markers_sec or []:
        col = marker_column(float(t), duration_sec=dur, width=width)
        glyph = "║" if (
            selected_marker_sec is not None
            and abs(float(t) - float(selected_marker_sec)) < 1e-6
        ) else "|"
        for y in range(height):
            grid[y][col] = glyph

    if playhead_sec is not None:
        col = marker_column(float(playhead_sec), duration_sec=dur, width=width)
        mid = height // 2
        grid[mid][col] = "▶"

    meta = {"viewport_cols": viewport_cols}
    if return_grid and return_meta:
        return grid, meta
    if return_grid:
        return grid
    lines = ["".join(row) for row in grid]
    return "\n".join(lines)


def slice_envelope_window(
    env: dict[str, Any],
    *,
    start_sec: float,
    end_sec: float,
) -> np.ndarray:
    """Return peak sub-array covering [start_sec, end_sec]."""
    peaks = np.asarray(env["peaks"], dtype=float)
    duration = float(env["duration_sec"])
    if duration <= 0 or peaks.size == 0:
        return peaks
    start_sec = max(0.0, min(duration, start_sec))
    end_sec = max(start_sec, min(duration, end_sec))
    i0 = int(start_sec / duration * peaks.size)
    i1 = int(end_sec / duration * peaks.size)
    i1 = max(i0 + 1, i1)
    return peaks[i0:i1]
