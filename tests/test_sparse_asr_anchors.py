"""Tests for sparse-ASR probe densification and long-segment onset hints."""

from dat_tracker.gemini_tracker import speech_anchor_cuts_with_probes
from dat_tracker.speech import long_segment_onset_candidates


def test_long_segment_onset_candidates_keeps_hallucinated_song_spans():
    segs = [
        {"start": 0.0, "end": 3.0, "text": "intro"},
        {"start": 165.4, "end": 382.6, "text": "fake song span"},
        {"start": 383.7, "end": 385.7, "text": "banter"},
        {"start": 406.0, "end": 890.6, "text": "another fake span"},
    ]
    onsets = long_segment_onset_candidates(segs, min_seg_sec=20.0)
    assert onsets == [165.4, 406.0]


def test_speech_anchor_cuts_with_probes_includes_long_onsets_when_sparse():
    segs = [
        {"start": 0.0, "end": 3.0, "text": "intro"},
        {"start": 165.4, "end": 382.6, "text": "fake song span"},
        {"start": 383.7, "end": 385.7, "text": "hi"},
        {"start": 386.5, "end": 393.4, "text": "banter"},
        {"start": 406.0, "end": 890.6, "text": "another fake span"},
        {"start": 890.6, "end": 893.2, "text": "thanks"},
    ]
    anchors, probes = speech_anchor_cuts_with_probes(
        segs,
        duration_sec=1188.0,
        max_gap_sec=240.0,
        probe_step_sec=90.0,
    )
    assert any(abs(a - 165.4) < 0.01 for a in anchors)
    assert any(abs(a - 406.0) < 0.01 for a in anchors)
    # Still have denser probes in the long remaining music span.
    assert any(600.0 < p < 750.0 for p in probes)
