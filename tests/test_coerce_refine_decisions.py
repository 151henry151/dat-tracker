"""Harden refine_decisions parsing when Gemini returns null times."""

from dat_tracker.gemini_tracker import coerce_refine_decision_times


def test_coerce_refine_decision_times_skips_nulls():
    assert coerce_refine_decision_times({"from_sec": 10.0, "to_sec": None}) is None
    assert coerce_refine_decision_times({"from_sec": None, "to_sec": 12.0}) is None
    assert coerce_refine_decision_times({"from_sec": 10.0, "to_sec": 12.5}) == (
        10.0,
        12.5,
    )
    assert coerce_refine_decision_times({"from_sec": 10.0}) == (10.0, 10.0)
