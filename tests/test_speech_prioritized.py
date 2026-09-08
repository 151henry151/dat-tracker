"""Tests for speech-island filtering and speech-prioritized boundary proposals."""

from dat_tracker.speech import (
    cuts_from_speech_islands,
    filter_plausible_speech_segments,
    merge_speech_islands,
    propose_speech_prioritized_cuts,
    snap_cuts_to_nearby,
)


def test_filter_plausible_speech_segments_drops_long_hallucinations():
    segs = [
        {"start": 215.0, "end": 224.0, "text": "banter"},
        {"start": 224.0, "end": 369.0, "text": "Hey, come on."},  # music span
        {"start": 370.0, "end": 384.0, "text": "encore ask"},
    ]
    kept = filter_plausible_speech_segments(segs, max_seg_sec=20.0)
    assert kept == [
        {"start": 215.0, "end": 224.0, "text": "banter"},
        {"start": 370.0, "end": 384.0, "text": "encore ask"},
    ]


def test_merge_speech_islands_joins_nearby_segments():
    segs = [
        {"start": 215.0, "end": 219.0, "text": "a"},
        {"start": 220.0, "end": 224.0, "text": "b"},
        {"start": 370.0, "end": 380.0, "text": "c"},
    ]
    islands = merge_speech_islands(segs, merge_gap_sec=3.0)
    assert islands == [
        {"start": 215.0, "end": 224.0, "text": "a b"},
        {"start": 370.0, "end": 380.0, "text": "c"},
    ]


def test_cuts_from_speech_islands_use_starts_and_endpoints():
    islands = [
        {"start": 0.0, "end": 6.0, "text": "intro"},
        {"start": 215.0, "end": 224.0, "text": "banter"},
        {"start": 370.0, "end": 396.0, "text": "ask"},
    ]
    cuts = cuts_from_speech_islands(islands, duration_sec=829.0, min_island_sec=1.0)
    assert cuts == [0.0, 215.0, 370.0, 829.0]


def test_snap_cuts_to_nearby_energy():
    snapped = snap_cuts_to_nearby(
        [215.0, 370.0],
        anchors=[0.0, 214.0, 375.0, 830.0],
        window_sec=8.0,
    )
    assert snapped == [214.0, 375.0]


def test_propose_speech_prioritized_fills_long_gaps_with_energy():
    # Whisper hallunication + real banter islands; one song→song gap without talk.
    segs = [
        {"start": 0.0, "end": 6.0, "text": "intro"},
        {"start": 215.0, "end": 224.0, "text": "banter"},
        {"start": 224.0, "end": 369.0, "text": "Hey, come on."},
        {"start": 370.0, "end": 384.0, "text": "ask"},
        {"start": 396.0, "end": 818.0, "text": "Oh, Jason Carter."},
        {"start": 819.0, "end": 826.0, "text": "credits"},
    ]
    energy = [0.0, 41.0, 203.0, 214.0, 375.0, 556.0, 687.0, 812.0, 830.0]
    cuts = propose_speech_prioritized_cuts(
        segs,
        energy_cuts=energy,
        duration_sec=830.0,
        max_seg_sec=20.0,
        merge_gap_sec=3.0,
        snap_window_sec=8.0,
        max_gap_sec=240.0,
        fill_min_separation_sec=90.0,
    )
    # Speech snaps near 214/375; long music gap 375→812 gets sparse energy fills.
    assert cuts[0] == 0.0
    assert cuts[-1] == 830.0
    assert 210.0 <= cuts[1] <= 220.0
    assert 365.0 <= cuts[2] <= 380.0
    assert any(640.0 <= c <= 700.0 for c in cuts)
