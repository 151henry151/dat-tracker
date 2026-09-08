"""Tests for comparing proposed track boundaries to Jon ground-truth cuts."""

from dat_tracker.boundaries import (
    boundary_f1,
    cuts_from_durations,
    list_track_flacs,
    parse_ffprobe_duration,
    reference_cuts_from_durations_map,
    summarize_comparison,
)


def test_cuts_from_durations_are_cumulative_starts_plus_end():
    # Three tracks of 10s, 20s, 5s → starts at 0, 10, 30 and end at 35.
    assert cuts_from_durations([10.0, 20.0, 5.0]) == [0.0, 10.0, 30.0, 35.0]


def test_boundary_f1_perfect_match():
    ref = [0.0, 10.0, 30.0, 35.0]
    metrics = boundary_f1(ref, ref, tolerance_sec=0.5)
    assert metrics["precision"] == 1.0
    assert metrics["recall"] == 1.0
    assert metrics["f1"] == 1.0
    assert metrics["matched"] == 4


def test_boundary_f1_within_tolerance():
    ref = [0.0, 10.0, 30.0]
    hyp = [0.05, 9.8, 30.4]
    metrics = boundary_f1(ref, hyp, tolerance_sec=0.5)
    assert metrics["f1"] == 1.0


def test_boundary_f1_missed_and_extra_cuts():
    ref = [0.0, 10.0, 20.0, 30.0]
    hyp = [0.0, 10.0, 30.0]  # missed mid cut
    metrics = boundary_f1(ref, hyp, tolerance_sec=0.25)
    assert metrics["matched"] == 3
    assert metrics["recall"] == 0.75
    assert metrics["precision"] == 1.0


def test_list_track_flacs_sorts_etree_names(tmp_path):
    names = [
        "jcb2002-08-02_t10.flac",
        "jcb2002-08-02_t02.flac",
        "jcb2002-08-02_t01.flac",
        "jcb2002-08-02.txt",
        "fingerprint.ffp.txt",
    ]
    for name in names:
        (tmp_path / name).write_bytes(b"")
    ordered = [p.name for p in list_track_flacs(tmp_path)]
    assert ordered == [
        "jcb2002-08-02_t01.flac",
        "jcb2002-08-02_t02.flac",
        "jcb2002-08-02_t10.flac",
    ]


def test_summarize_comparison_includes_track_count_delta():
    summary = summarize_comparison(
        reference_cuts=[0.0, 10.0, 20.0],
        hypothesis_cuts=[0.0, 10.0],
        tolerance_sec=0.5,
    )
    assert summary["reference_tracks"] == 2
    assert summary["hypothesis_tracks"] == 1
    assert summary["track_count_delta"] == -1
    assert "f1" in summary


def test_parse_ffprobe_duration_reads_format_duration():
    payload = {"format": {"duration": "123.456000"}}
    assert parse_ffprobe_duration(payload) == 123.456


def test_reference_cuts_from_durations_map_follows_sorted_paths(tmp_path):
    a = tmp_path / "show_t01.flac"
    b = tmp_path / "show_t02.flac"
    a.write_bytes(b"")
    b.write_bytes(b"")
    cuts = reference_cuts_from_durations_map({a: 10.0, b: 5.0})
    assert cuts == [0.0, 10.0, 15.0]
