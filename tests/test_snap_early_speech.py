"""Tests for snapping clearly-early cuts forward onto nearby speech onsets."""

from dat_tracker.refine_cuts import snap_clearly_early_cuts_to_speech


def test_snap_clearly_early_cuts_to_speech_moves_cut_in_applause_window():
    # Cut at song end / mid-applause; banter onset ~25s later should win.
    cuts = [0.0, 430.0, 1000.0]
    islands = [{"start": 451.0, "end": 460.0}]
    snapped = snap_clearly_early_cuts_to_speech(
        cuts,
        speech_islands=islands,
        duration_sec=1000.0,
        min_early_sec=15.0,
        max_early_sec=35.0,
    )
    assert any(abs(c - 451.0) < 0.01 for c in snapped)
    assert not any(abs(c - 430.0) < 0.01 for c in snapped)


def test_snap_clearly_early_cuts_to_speech_ignores_near_and_far_onsets():
    cuts = [0.0, 400.0, 1000.0]
    islands = [
        {"start": 405.0, "end": 410.0},  # too close (<15s)
        {"start": 460.0, "end": 470.0},  # too far (>35s)
    ]
    snapped = snap_clearly_early_cuts_to_speech(
        cuts,
        speech_islands=islands,
        duration_sec=1000.0,
        min_early_sec=15.0,
        max_early_sec=35.0,
    )
    assert any(abs(c - 400.0) < 0.01 for c in snapped)


def test_snap_clearly_early_cuts_to_speech_picks_first_onset_not_last():
    cuts = [0.0, 200.0, 1000.0]
    islands = [
        {"start": 220.0, "end": 225.0},
        {"start": 230.0, "end": 235.0},
    ]
    snapped = snap_clearly_early_cuts_to_speech(
        cuts,
        speech_islands=islands,
        duration_sec=1000.0,
        min_early_sec=15.0,
        max_early_sec=35.0,
    )
    assert any(abs(c - 220.0) < 0.01 for c in snapped)
    assert not any(abs(c - 230.0) < 0.01 for c in snapped)


def test_snap_clearly_early_cuts_leaves_cut_already_on_speech_onset():
    # Correct song-start cut must not jump to mid-song vocals ~27s later.
    cuts = [0.0, 1044.0, 2000.0]
    islands = [
        {"start": 1044.0, "end": 1050.0},
        {"start": 1070.8, "end": 1075.0},
    ]
    snapped = snap_clearly_early_cuts_to_speech(
        cuts,
        speech_islands=islands,
        duration_sec=2000.0,
        min_early_sec=15.0,
        max_early_sec=35.0,
    )
    assert any(abs(c - 1044.0) < 0.01 for c in snapped)
    assert not any(abs(c - 1070.8) < 0.01 for c in snapped)
