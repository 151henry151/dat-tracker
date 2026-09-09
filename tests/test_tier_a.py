"""Tests for building Tier A continuous extracts from aligned raw↔Jon pairs."""

from pathlib import Path

from dat_tracker.tier_a import tier_a_known_cuts_from_reference


def test_tier_a_known_cuts_are_relative_to_extract_start():
    # Reference cuts are show-local (0..duration). Extract starts at raw offset.
    ref = [0.0, 100.0, 250.0, 400.0]
    assert tier_a_known_cuts_from_reference(ref) == [0.0, 100.0, 250.0, 400.0]
