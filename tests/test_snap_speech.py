"""Tests for snapping cuts forward onto nearby speech onsets."""

from dat_tracker.refine_cuts import snap_cuts_forward_to_speech


def test_snap_cuts_forward_to_speech_picks_last_onset_in_window():
    islands = [
        {"start": 447.1, "end": 453.0, "text": "thanks"},
        {"start": 458.5, "end": 466.0, "text": "song book"},
        {"start": 500.0, "end": 510.0, "text": "later"},
    ]
    snapped = snap_cuts_forward_to_speech(
        [0.0, 439.0, 800.0],
        speech_islands=islands,
        duration_sec=800.0,
        look_ahead_sec=35.0,
    )
    assert snapped[0] == 0.0
    assert snapped[-1] == 800.0
    assert abs(snapped[1] - 458.5) < 0.01
