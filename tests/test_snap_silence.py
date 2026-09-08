"""Tests for snapping cuts onto nearby silence ends."""

from dat_tracker.refine_cuts import snap_cuts_to_nearby_silence_ends


def test_snap_cuts_to_nearby_silence_ends_pulls_clearly_late_cut_back():
    # Gemini placed ~688; silence end ~643 is ≥20s earlier → snap.
    cuts = [0.0, 301.0, 688.7, 944.0, 3287.0]
    silence_ends = [250.0, 643.4, 900.0, 1825.0]
    snapped = snap_cuts_to_nearby_silence_ends(
        cuts,
        silence_ends=silence_ends,
        duration_sec=3287.0,
        look_back_sec=55.0,
        min_late_sec=20.0,
    )
    assert any(abs(c - 643.4) < 0.01 for c in snapped)
    assert not any(abs(c - 688.7) < 0.01 for c in snapped)


def test_snap_cuts_to_nearby_silence_ends_ignores_nearly_aligned_cuts():
    # Cut only a few seconds after a silence end — leave it alone.
    cuts = [0.0, 261.0, 1672.0, 3883.0]
    silence_ends = [257.4, 1350.1]
    snapped = snap_cuts_to_nearby_silence_ends(
        cuts,
        silence_ends=silence_ends,
        duration_sec=3883.0,
        look_back_sec=55.0,
        min_late_sec=20.0,
    )
    assert any(abs(c - 261.0) < 0.01 for c in snapped)


def test_snap_cuts_to_nearby_silence_ends_leaves_lonely_cuts():
    cuts = [0.0, 500.0, 1000.0]
    snapped = snap_cuts_to_nearby_silence_ends(
        cuts,
        silence_ends=[100.0],
        duration_sec=1000.0,
    )
    assert snapped == [0.0, 500.0, 1000.0]
