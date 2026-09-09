"""Tests for snapping mid cuts onto nearby listen centers."""

from dat_tracker.refine_cuts import snap_cuts_to_nearby_listen_centers


def test_snap_cuts_to_nearby_listen_centers_moves_clearly_offset_cut():
    cuts = [0.0, 271.4, 800.0, 1000.0]
    centers = [0.0, 245.0, 750.0, 1000.0]
    snapped = snap_cuts_to_nearby_listen_centers(
        cuts,
        listen_centers=centers,
        duration_sec=1000.0,
        radius_sec=40.0,
        min_delta_sec=8.0,
    )
    assert any(abs(c - 245.0) < 0.01 for c in snapped)
    assert not any(abs(c - 271.4) < 0.01 for c in snapped)


def test_snap_cuts_to_nearby_listen_centers_leaves_nearly_aligned_cuts():
    cuts = [0.0, 250.0, 1000.0]
    centers = [245.0, 800.0]
    snapped = snap_cuts_to_nearby_listen_centers(
        cuts,
        listen_centers=centers,
        duration_sec=1000.0,
        radius_sec=40.0,
        min_delta_sec=8.0,
    )
    assert any(abs(c - 250.0) < 0.01 for c in snapped)
