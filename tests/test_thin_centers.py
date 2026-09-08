"""Tests for thinning listen centers on long, speech-dense shows."""

from dat_tracker.refine_cuts import (
    adaptive_speech_snap_look_ahead_sec,
    ensure_endpoint_cuts,
    thin_listen_centers,
)


def test_thin_listen_centers_caps_dense_anchors():
    # Dense banter-like anchors every ~40s on a long show (>1.5x target → thin).
    anchors = [0.0] + [float(i) for i in range(40, 3200, 40)] + [3287.0]
    probes = [float(i) + 20.0 for i in range(40, 3200, 120)]
    a2, p2 = thin_listen_centers(
        anchors=anchors,
        probes=probes,
        duration_sec=3287.0,
        target_mid_cuts=14,
    )
    mid = [c for c in a2 if 0.05 < c < 3286]
    assert len(mid) <= 14
    assert a2[0] == 0.0 and abs(a2[-1] - 3287.0) < 0.05
    assert len(p2) <= len(probes)


def test_thin_listen_centers_skips_when_only_mildly_dense():
    # 16 mids vs target 14 → below 1.5x threshold → unchanged count.
    anchors = [0.0] + [float(200 * i) for i in range(1, 17)] + [3600.0]
    a2, _p2 = thin_listen_centers(
        anchors=anchors,
        probes=[],
        duration_sec=3600.0,
        target_mid_cuts=14,
    )
    assert len(a2) == len(sorted(set(anchors)))


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
