"""Tests for speech-segment derived boundary candidates."""

from dat_tracker.speech import cuts_from_speech_segments, parse_whisper_segments


def test_parse_whisper_segments_reads_start_end_text():
    payload = {
        "segments": [
            {"start": 1.0, "end": 3.5, "text": " hello "},
            {"start": 40.0, "end": 42.0, "text": "thanks"},
        ]
    }
    segs = parse_whisper_segments(payload)
    assert segs == [
        {"start": 1.0, "end": 3.5, "text": "hello"},
        {"start": 40.0, "end": 42.0, "text": "thanks"},
    ]


def test_cuts_from_speech_segments_emit_edges_and_endpoints():
    segs = [
        {"start": 5.0, "end": 12.0, "text": "banter"},
        {"start": 60.0, "end": 65.0, "text": "intro"},
    ]
    cuts = cuts_from_speech_segments(segs, duration_sec=100.0, min_seg_sec=1.0)
    assert cuts == [0.0, 5.0, 12.0, 60.0, 65.0, 100.0]


def test_cuts_from_speech_segments_drops_tiny_blips():
    segs = [{"start": 10.0, "end": 10.2, "text": "uh"}]
    cuts = cuts_from_speech_segments(segs, duration_sec=50.0, min_seg_sec=0.5)
    assert cuts == [0.0, 50.0]
