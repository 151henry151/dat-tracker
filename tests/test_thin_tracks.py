"""Tests for thinning excess cuts toward a duration-based track budget."""

from dat_tracker.refine_cuts import adaptive_max_tracks, thin_cuts_to_max_tracks


def test_adaptive_max_tracks_scales_with_duration():
    assert adaptive_max_tracks(800.0) == 4  # floor
    assert adaptive_max_tracks(1200.0) == 5
    assert adaptive_max_tracks(3287.0) == 14
    assert adaptive_max_tracks(3883.0) == 16


def test_thin_cuts_to_max_tracks_merges_shortest_segments():
    # 13 tracks; tightly sandwiched false cut at 496 should go before 643.
    cuts = [
        0.0,
        250.0,
        496.0,
        643.0,
        895.0,
        1101.0,
        1314.0,
        1470.0,
        1797.0,
        2128.0,
        2299.0,
        2513.0,
        3180.0,
        3287.0,
    ]
    assert len(cuts) - 1 == 13
    thinned = thin_cuts_to_max_tracks(cuts, max_tracks=10)
    assert thinned[0] == 0.0 and abs(thinned[-1] - 3287.0) < 0.05
    assert len(thinned) - 1 == 10
    assert 643.0 in thinned
    assert 496.0 not in thinned


def test_thin_cuts_to_max_tracks_noop_when_already_within_budget():
    cuts = [0.0, 200.0, 400.0, 829.0]
    assert thin_cuts_to_max_tracks(cuts, max_tracks=10) == cuts
