"""Tests for playback window helpers (no hardware required)."""

from __future__ import annotations

import pytest

from dat_tracker.audio_playback import loop_window_around_cut, clamp_play_range


def test_loop_window_around_cut_centers_with_padding():
    start, end = loop_window_around_cut(
        cut_sec=50.0,
        duration_sec=100.0,
        half_window_sec=8.0,
    )
    assert start == pytest.approx(42.0)
    assert end == pytest.approx(58.0)


def test_loop_window_clamps_at_show_edges():
    start, end = loop_window_around_cut(
        cut_sec=2.0,
        duration_sec=100.0,
        half_window_sec=8.0,
    )
    assert start == 0.0
    assert end == pytest.approx(10.0)

    start, end = loop_window_around_cut(
        cut_sec=98.0,
        duration_sec=100.0,
        half_window_sec=8.0,
    )
    assert start == pytest.approx(90.0)
    assert end == 100.0


def test_clamp_play_range():
    assert clamp_play_range(-1.0, 5.0, duration_sec=10.0) == (0.0, 5.0)
    assert clamp_play_range(8.0, 12.0, duration_sec=10.0) == (8.0, 10.0)
    assert clamp_play_range(5.0, 5.0, duration_sec=10.0) == (5.0, 5.01)
