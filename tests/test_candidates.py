"""Tests for fusing silence and energy boundary candidates."""

from dat_tracker.candidates import fuse_candidate_cuts, label_support


def test_fuse_candidate_cuts_merges_nearby_proposals():
    silence = [0.0, 10.0, 30.5, 100.0]
    energy = [0.0, 10.2, 50.0, 100.0]
    fused = fuse_candidate_cuts(
        {"silence": silence, "energy": energy},
        merge_tolerance_sec=0.5,
    )
    assert fused == [0.0, 10.1, 30.5, 50.0, 100.0]


def test_fuse_prefers_intersection_when_requested():
    silence = [0.0, 10.0, 40.0, 100.0]
    energy = [0.0, 10.3, 70.0, 100.0]
    fused = fuse_candidate_cuts(
        {"silence": silence, "energy": energy},
        merge_tolerance_sec=0.5,
        require_sources=("silence", "energy"),
    )
    # endpoints always kept; only 10.x is supported by both
    assert fused == [0.0, 10.15, 100.0]


def test_label_support_reports_which_sources_hit():
    support = label_support(
        cut_sec=10.1,
        sources={"silence": [10.0], "energy": [10.2], "speech": [50.0]},
        tolerance_sec=0.25,
    )
    assert support == {"silence", "energy"}
