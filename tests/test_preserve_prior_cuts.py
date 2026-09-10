"""Tests for preserving well-spaced prior cuts after Pro/refine collapse."""

from dat_tracker.refine_cuts import preserve_well_spaced_prior_cuts


def test_preserve_well_spaced_prior_cuts_reinserts_dropped_mids():
    prior = [0.0, 100.0, 300.0, 500.0, 700.0, 1000.0]
    # Pro collapsed to 3 tracks by dropping 300 and 500.
    new = [0.0, 100.0, 700.0, 1000.0]
    out = preserve_well_spaced_prior_cuts(
        prior, new, duration_sec=1000.0, min_separation_sec=45.0
    )
    assert 300.0 in out
    assert 500.0 in out
    assert out[0] == 0.0 and out[-1] == 1000.0


def test_preserve_well_spaced_prior_cuts_skips_near_duplicates():
    prior = [0.0, 100.0, 310.0, 1000.0]
    new = [0.0, 100.0, 300.0, 1000.0]
    out = preserve_well_spaced_prior_cuts(
        prior, new, duration_sec=1000.0, min_separation_sec=45.0
    )
    # 310 is within 45s of 300 → do not re-insert.
    assert 310.0 not in out
    assert 300.0 in out
