"""Tests for merging gap-fill inserts into an existing cut list."""

from dat_tracker.refine_cuts import merge_gap_fill_cuts


def test_merge_gap_fill_cuts_inserts_new_mids_with_separation():
    existing = [0.0, 404.0, 1070.0, 2600.0]
    proposed = [0.0, 404.0, 687.0, 900.0, 1070.0, 1445.0, 2600.0]
    merged = merge_gap_fill_cuts(
        existing,
        proposed,
        duration_sec=2600.0,
        min_separation_sec=25.0,
    )
    assert merged[0] == 0.0 and abs(merged[-1] - 2600.0) < 0.05
    assert any(abs(c - 687.0) < 0.01 for c in merged)
    assert any(abs(c - 1445.0) < 0.01 for c in merged)


def test_merge_gap_fill_cuts_drops_near_duplicates():
    existing = [0.0, 400.0, 1000.0]
    proposed = [0.0, 410.0, 1000.0]
    merged = merge_gap_fill_cuts(
        existing,
        proposed,
        duration_sec=1000.0,
        min_separation_sec=25.0,
    )
    # 400 and 410 collapse; keep earlier then later spacing.
    assert len(merged) == 3
