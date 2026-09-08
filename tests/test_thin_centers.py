"""Tests for thinning listen centers on long, speech-dense shows."""

from dat_tracker.refine_cuts import (
    adaptive_speech_snap_look_ahead_sec,
    ensure_endpoint_cuts,
    thin_listen_centers,
)


def test_thin_listen_centers_keeps_anchors_but_caps_probes_on_long_shows():
    # Dense banter-like anchors must stay (dropping them kills true boundaries).
    anchors = [0.0] + [float(i) for i in range(40, 3200, 40)] + [3287.0]
    probes = [float(i) + 20.0 for i in range(40, 3200, 80)]
    a2, p2 = thin_listen_centers(
        anchors=anchors,
        probes=probes,
        duration_sec=3287.0,
        target_mid_cuts=14,
    )
    assert a2[0] == 0.0 and abs(a2[-1] - 3287.0) < 0.05
    mid_in = {a for a in anchors if 0.05 < a < 3286}
    mid_out = {a for a in a2 if 0.05 < a < 3286}
    assert mid_in <= mid_out
    assert len(p2) < len(probes)
    assert len(p2) <= max(2, 14)


def test_thin_listen_centers_skips_short_shows_even_if_dense():
    # Merlefest-length (~20 min) keeps anchors and probes.
    anchors = [0.0] + [float(i) for i in range(40, 1150, 40)] + [1192.0]
    probes = [60.0, 200.0, 400.0, 800.0]
    a2, p2 = thin_listen_centers(
        anchors=anchors,
        probes=probes,
        duration_sec=1192.0,
        target_mid_cuts=5,
    )
    assert len(a2) == len(sorted(set(anchors)))
    assert p2 == sorted(probes)


def test_adaptive_speech_snap_look_ahead_grows_on_long_shows():
    assert adaptive_speech_snap_look_ahead_sec(800.0) == 45.0
    assert adaptive_speech_snap_look_ahead_sec(2500.0) == 90.0


def test_ensure_endpoint_cuts_adds_missing_zero_and_duration():
    assert ensure_endpoint_cuts([88.4, 260.8], duration_sec=1000.0) == [
        0.0,
        88.4,
        260.8,
        1000.0,
    ]
