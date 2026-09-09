"""Gap-fill should only run when the plan looks under-segmented."""

from dat_tracker.track_show import should_run_gap_fill


def test_should_run_gap_fill_when_max_segment_long():
    assert should_run_gap_fill(
        cuts_sec=[0.0, 400.0, 2000.0],
        duration_sec=2000.0,
        max_seg_sec=480.0,
    )


def test_should_run_gap_fill_skips_well_segmented_plans():
    assert not should_run_gap_fill(
        cuts_sec=[0.0, 200.0, 400.0, 600.0, 800.0, 1000.0],
        duration_sec=1000.0,
        max_seg_sec=480.0,
    )
