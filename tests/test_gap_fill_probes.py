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


def test_overlong_gap_probe_centers_falls_back_to_geometric_target_when_candidates_far():
    # Same idea as above, but with a *dense* candidate pool (more than
    # sparse_candidate_limit), which keeps the original nearest-to-target
    # selection path instead of the "probe every sparse candidate" path
    # exercised by test_overlong_gap_probe_centers_probes_all_sparse_candidates
    # below. All five candidates are far from any of the evenly spaced
    # targets, so each target should fall back to its own untethered
    # geometric position rather than snap to a distant candidate.
    cuts = [0.0, 100.0, 2100.0, 2200.0]
    candidates = [160.0, 500.0, 1000.0, 1600.0, 2040.0]
    probes = overlong_gap_probe_centers(
        cuts,
        duration_sec=2200.0,
        candidate_centers=candidates,
        max_seg_sec=650.0,
        min_edge_sec=45.0,
        max_probes_per_gap=3,
        sparse_candidate_limit=4,
    )
    # gap is 2000s over max_seg_sec=650 -> 3 evenly spaced targets at
    # 100+500, 100+1000, 100+1500 = 600, 1100, 1600. None of the candidates
    # sit within the default 90s offset of 600 or 1100, so those fall back
    # to the raw targets; 1600 has an exact-match candidate and is kept.
    assert 600.0 in probes
    assert 1100.0 in probes
    assert 1600.0 in probes


def test_overlong_gap_probe_centers_probes_all_sparse_candidates():
    # Real train miss (ymsb2007-02-24.flac16): the true missing boundary
    # (331.5s) sat on the second-nearest-to-midpoint candidate (364.0), not
    # the nearest one (266.0) that the old target-matching logic picked.
    # With only 3 candidates in this gap (well under sparse_candidate_limit),
    # probe all of them instead of guessing which one is "closest enough" to
    # a geometric midpoint.
    cuts = [0.0, 88.5, 432.0]
    candidates = [155.0, 266.0, 364.0]
    probes = overlong_gap_probe_centers(
        cuts,
        duration_sec=432.0,
        candidate_centers=candidates,
        max_seg_sec=320.0,
        min_edge_sec=45.0,
        max_probes_per_gap=2,
    )
    assert probes == [155.0, 266.0, 364.0]


def test_overlong_gap_probe_centers_keeps_dense_gap_conservative():
    # Real precision risk (sbb2001-04-27.flac16): a legitimately continuous
    # ~590s song had six already-rejected classical candidates inside it.
    # Probing all of them would give the model six chances to hallucinate a
    # boundary in one real song, so a dense gap keeps the original
    # single-nearest-to-target selection instead of the sparse "probe all"
    # path.
    cuts = [0.0, 375.3, 536.4, 620.4, 1210.2]
    candidates = [644.9, 737.0, 869.0, 893.0, 992.0, 1185.0]
    probes = overlong_gap_probe_centers(
        cuts,
        duration_sec=1210.2,
        candidate_centers=candidates,
        max_seg_sec=320.0,
        min_edge_sec=45.0,
        max_probes_per_gap=1,
    )
    # 4 candidates fit inside min_edge_sec of the 620.4->1210.2 gap — above
    # sparse_candidate_limit (3), so that gap stays on the conservative
    # single-nearest-to-target path instead of probing every one of them
    # (the earlier 0->375.3 gap also qualifies as overlong and contributes
    # its own unrelated fallback probe, which this assertion ignores).
    probes_in_long_gap = [p for p in probes if p > 620.4]
    assert len(probes_in_long_gap) == 1


def test_overlong_gap_probe_centers_noop_when_segments_short():
    cuts = [0.0, 200.0, 400.0, 600.0]
    probes = overlong_gap_probe_centers(
        cuts,
        duration_sec=600.0,
        candidate_centers=[100.0, 300.0, 500.0],
        max_seg_sec=420.0,
    )
    assert probes == []
