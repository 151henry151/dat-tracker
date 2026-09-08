"""Tests for ffmpeg silencedetect-based boundary proposals."""

from dat_tracker.silence import (
    parse_silencedetect_lines,
    propose_cuts_from_silences,
    silence_midpoints,
)


def test_parse_silencedetect_lines_pairs_start_and_end():
    lines = [
        "[silencedetect @ 0x1] silence_start: 12.5",
        "[silencedetect @ 0x1] silence_end: 14.0 | silence_duration: 1.5",
        "frame=1",
        "[silencedetect @ 0x1] silence_start: 100.0",
        "[silencedetect @ 0x1] silence_end: 103.25 | silence_duration: 3.25",
    ]
    regions = parse_silencedetect_lines(lines)
    assert regions == [(12.5, 14.0), (100.0, 103.25)]


def test_silence_midpoints():
    assert silence_midpoints([(10.0, 12.0), (20.0, 21.0)]) == [11.0, 20.5]


def test_propose_cuts_from_silences_includes_start_end_and_filtered_mids():
    cuts = propose_cuts_from_silences(
        silence_regions=[(5.0, 6.0), (50.0, 52.0), (90.0, 91.0)],
        duration_sec=100.0,
        min_silence_sec=1.5,
        pad_sec=0.0,
    )
    # 5-6s region too short; keep 50-52 midpoint; 90-91 too short
    assert cuts == [0.0, 51.0, 100.0]


def test_propose_cuts_respects_pad_near_edges():
    cuts = propose_cuts_from_silences(
        silence_regions=[(0.2, 2.2), (40.0, 42.0), (98.0, 99.5)],
        duration_sec=100.0,
        min_silence_sec=1.0,
        pad_sec=3.0,
    )
    # Edge silences within pad dropped; keep middle
    assert cuts == [0.0, 41.0, 100.0]
