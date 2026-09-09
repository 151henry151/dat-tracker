"""Tests for adaptive Gemini refine listen windows."""

from dat_tracker.refine_cuts import adaptive_refine_half_window_sec


def test_adaptive_refine_half_window_grows_on_long_shows():
    assert adaptive_refine_half_window_sec(800.0) == 20.0
    assert adaptive_refine_half_window_sec(1500.0) == 40.0
    assert adaptive_refine_half_window_sec(2500.0) == 50.0
