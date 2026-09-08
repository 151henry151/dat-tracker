"""Tests for near-duplicate cut merging and energy-assisted gap probes."""

from dat_tracker.refine_cuts import merge_near_duplicate_cuts
from dat_tracker.gemini_tracker import merge_energy_into_probes


def test_merge_near_duplicate_cuts_keeps_later_in_cluster():
    cuts = [0.0, 383.7, 406.0, 890.6, 895.5, 1188.0]
    merged = merge_near_duplicate_cuts(cuts, min_separation_sec=20.0)
    # 383.7 and 406 are >20s apart → both kept; 890.6/895.5 collapse to later.
    assert merged == [0.0, 383.7, 406.0, 895.5, 1188.0]


def test_merge_near_duplicate_cuts_preserves_well_spaced():
    cuts = [0.0, 168.0, 407.0, 684.0, 898.0, 1188.0]
    assert merge_near_duplicate_cuts(cuts, min_separation_sec=20.0) == cuts


def test_merge_energy_into_probes_adds_peaks_in_long_gaps():
    anchors = [0.0, 406.0, 890.0, 1188.0]
    energy = [0.0, 200.0, 684.0, 700.0, 1000.0, 1188.0]
    probes = merge_energy_into_probes(
        anchors=anchors,
        existing_probes=[496.0, 586.0],
        energy_cuts=energy,
        min_gap_sec=240.0,
        edge_pad_sec=20.0,
    )
    assert any(abs(p - 684.0) < 0.01 for p in probes)
    # Do not re-add peaks that are basically anchors.
    assert not any(abs(p - 406.0) < 0.01 for p in probes)


def test_merge_energy_into_anchors_promotes_peaks_in_medium_gaps():
    from dat_tracker.gemini_tracker import merge_energy_into_anchors

    anchors = [0.0, 500.0, 1000.0]
    out = merge_energy_into_anchors(
        anchors=anchors,
        energy_cuts=[241.0, 502.0, 780.0],
        min_gap_sec=90.0,
        near_anchor_sec=30.0,
    )
    assert any(abs(a - 241.0) < 0.01 for a in out)
    assert any(abs(a - 780.0) < 0.01 for a in out)
    # Too close to existing speech anchor.
    assert not any(abs(a - 502.0) < 0.01 for a in out)
