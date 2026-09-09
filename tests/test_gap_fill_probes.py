"""Tests for proposing insert probes inside overlong track segments."""

from dat_tracker.refine_cuts import overlong_gap_probe_centers


def test_overlong_gap_probe_centers_picks_candidates_inside_long_gaps():
    cuts = [0.0, 404.0, 1070.0, 2600.0]
    candidates = [173.0, 250.0, 687.0, 900.0, 1445.0, 2000.0]
    probes = overlong_gap_probe_centers(
        cuts,
        duration_sec=2600.0,
        candidate_centers=candidates,
        max_seg_sec=420.0,
        min_edge_sec=45.0,
        max_probes_per_gap=3,
    )
    # Gap 404→1070 (~666s) should pick near 687; gap 1070→2600 should pick mids.
    assert any(abs(p - 687.0) < 1.0 for p in probes)
    assert all(p not in {0.0, 404.0, 1070.0, 2600.0} for p in probes)
    assert all(45.0 < p < 2555.0 for p in probes)


def test_overlong_gap_probe_centers_noop_when_segments_short():
    cuts = [0.0, 200.0, 400.0, 600.0]
    probes = overlong_gap_probe_centers(
        cuts,
        duration_sec=600.0,
        candidate_centers=[100.0, 300.0, 500.0],
        max_seg_sec=420.0,
    )
    assert probes == []
