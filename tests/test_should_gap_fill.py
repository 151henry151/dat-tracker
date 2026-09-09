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


def test_should_escalate_to_pro_skips_short_ok_plans():
    from dat_tracker.track_show import should_escalate_to_pro

    # Sam Bush-like: ~20 min, one longer mid segment, track count OK.
    assert not should_escalate_to_pro(
        cuts_sec=[0.0, 375.0, 536.0, 645.0, 1210.0],
        duration_sec=1210.0,
        max_seg_sec=600.0,
    )


def test_should_escalate_to_pro_on_long_underseg():
    from dat_tracker.track_show import should_escalate_to_pro

    assert should_escalate_to_pro(
        cuts_sec=[0.0, 404.0, 2600.0],
        duration_sec=2600.0,
        max_seg_sec=600.0,
    )
