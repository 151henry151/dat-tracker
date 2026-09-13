"""Tests for waveform envelope compute/cache and render helpers."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

numpy = pytest.importorskip("numpy")

from dat_tracker.waveform import (  # noqa: E402
    compute_peak_envelope,
    load_or_build_envelope,
    marker_column,
    render_envelope_line,
    render_envelope_panel,
    render_time_ruler,
)


def _make_tone_flac(path: Path, *, duration: float = 1.0, freq: float = 440.0) -> None:
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency={freq}:sample_rate=8000:duration={duration}",
            "-c:a",
            "flac",
            str(path),
        ],
        check=True,
        capture_output=True,
    )


def test_compute_peak_envelope_length_and_range(tmp_path: Path):
    flac = tmp_path / "tone.flac"
    _make_tone_flac(flac, duration=1.0)
    env = compute_peak_envelope(flac, bucket_count=100)
    assert env["bucket_count"] == 100
    assert len(env["peaks"]) == 100
    assert env["duration_sec"] == pytest.approx(1.0, abs=0.05)
    peaks = numpy.asarray(env["peaks"], dtype=float)
    assert peaks.min() >= 0.0
    assert peaks.max() <= 1.0
    assert peaks.max() > 0.1


def test_load_or_build_envelope_caches(tmp_path: Path):
    flac = tmp_path / "tone.flac"
    cache = tmp_path / "waveform_envelope.npz"
    _make_tone_flac(flac, duration=0.5)
    first = load_or_build_envelope(flac, cache_path=cache, bucket_count=50)
    assert cache.is_file()
    mtime = cache.stat().st_mtime
    second = load_or_build_envelope(flac, cache_path=cache, bucket_count=50)
    assert cache.stat().st_mtime == mtime
    assert list(first["peaks"]) == list(second["peaks"])


def test_render_envelope_line_width_and_markers():
    peaks = [0.0, 0.5, 1.0, 0.25]
    line = render_envelope_line(peaks, width=8, markers_sec=[0.0, 1.5], duration_sec=2.0)
    assert len(line) == 8
    # Marker columns for 0.0 and 1.5s on a 2.0s span of width 8.
    assert marker_column(0.0, duration_sec=2.0, width=8) == 0
    assert marker_column(1.5, duration_sec=2.0, width=8) == 5
    assert marker_column(2.0, duration_sec=2.0, width=8) == 7


def test_render_envelope_panel_dimensions_and_markers():
    peaks = [0.0, 0.25, 1.0, 0.5] * 4
    grid = render_envelope_panel(
        peaks,
        width=16,
        height=5,
        markers_sec=[0.0, 2.0],
        duration_sec=4.0,
        return_grid=True,
    )
    assert len(grid) == 5
    assert all(len(row) == 16 for row in grid)
    # Markers are full-height columns.
    c0 = marker_column(0.0, duration_sec=4.0, width=16)
    c1 = marker_column(2.0, duration_sec=4.0, width=16)
    for row in grid:
        assert row[c0] == "|"
        assert row[c1] == "|"


def test_render_envelope_panel_sqrt_gives_quiet_fewer_rows():
    # One loud peak column and one quiet; quiet should occupy fewer non-space cells.
    peaks = [0.05] * 8 + [1.0] * 8
    grid = render_envelope_panel(
        peaks, width=16, height=8, duration_sec=1.0, return_grid=True
    )
    quiet_filled = sum(1 for row in grid if row[2] not in (" ", "|", "▶"))
    loud_filled = sum(1 for row in grid if row[12] not in (" ", "|", "▶"))
    assert loud_filled > quiet_filled


def test_render_envelope_panel_viewport_and_playhead():
    peaks = [0.5] * 20
    grid, meta = render_envelope_panel(
        peaks,
        width=20,
        height=3,
        duration_sec=100.0,
        playhead_sec=50.0,
        viewport_sec=(25.0, 75.0),
        return_grid=True,
        return_meta=True,
    )
    v0 = marker_column(25.0, duration_sec=100.0, width=20)
    v1 = marker_column(75.0, duration_sec=100.0, width=20)
    assert meta["viewport_cols"] == (v0, v1)
    ph = marker_column(50.0, duration_sec=100.0, width=20)
    assert any(row[ph] == "▶" for row in grid)


def test_render_time_ruler_width():
    ruler = render_time_ruler(duration_sec=120.0, width=40)
    assert len(ruler) == 40
    assert "0:00" in ruler
    assert "2:00" in ruler or "1:" in ruler
