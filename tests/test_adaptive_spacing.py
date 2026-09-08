"""Tests for duration-adaptive minimum cut spacing."""

from dat_tracker.refine_cuts import adaptive_min_separation_sec, merge_near_duplicate_cuts


def test_adaptive_min_separation_grows_with_duration():
    assert adaptive_min_separation_sec(800.0) == 20.0
    assert adaptive_min_separation_sec(1500.0) == 45.0
    assert adaptive_min_separation_sec(3500.0) == 90.0


def test_adaptive_merge_reduces_ymsb_style_oversegmentation():
    # Synthetic over-segmented long show; known-like spacing ~3–6 minutes.
    cuts = [
        0.0,
        260.0,
        408.0,
        617.0,
        876.0,
        942.0,
        1109.0,
        1299.0,
        1606.0,
        1669.0,
        1878.0,
        2242.0,
        2734.0,
        2808.0,
        3169.0,
        3360.0,
        3883.0,
    ]
    sep = adaptive_min_separation_sec(3883.0)
    merged = merge_near_duplicate_cuts(cuts, min_separation_sec=sep)
    assert sep == 90.0
    assert len(merged) < len(cuts)
    assert len(merged) <= 14
