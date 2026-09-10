"""Tests for early-cut polish onto forward silence ends (next-track starts)."""

from dat_tracker.refine_cuts import polish_early_cuts_to_silence_ends


def test_polish_early_cuts_moves_to_last_confirmed_silence_end():
    # crnml-shaped: cut mid-applause; true start is last silence with confirm after.
    cuts = [0.0, 228.5, 430.5, 1000.0]
    silence_ends = [200.0, 236.9, 240.4, 244.7, 400.0, 447.3, 452.2, 900.0]
    # Confirmations: energy/speech just after the real next-track silences.
    confirm_times = [245.0, 453.0]
    polished = polish_early_cuts_to_silence_ends(
        cuts,
        silence_ends=silence_ends,
        duration_sec=1000.0,
        min_early_sec=12.0,
        max_early_sec=40.0,
        confirm_times=confirm_times,
        confirm_within_sec=8.0,
    )
    assert polished[1] == 244.7
    assert polished[2] == 452.2


def test_polish_early_cuts_skips_when_already_near_confirmed_silence_end():
    # Already parked on a confirmed transition silence — do not yank forward.
    cuts = [0.0, 245.0, 500.0]
    silence_ends = [244.5, 260.0, 400.0]
    polished = polish_early_cuts_to_silence_ends(
        cuts,
        silence_ends=silence_ends,
        duration_sec=500.0,
        already_near_sec=5.0,
        confirm_times=[245.5],  # confirms the nearby 244.5
    )
    assert polished[1] == 245.0


def test_polish_early_cuts_ignores_unconfirmed_nearby_silence_trap():
    # jcb-shaped: spurious silence blip within already_near of an early cut must
    # not block a walk to a later confirmed next-track start.
    cuts = [0.0, 605.0, 1334.0, 4000.0]
    silence_ends = [600.0, 607.0, 643.0, 650.0, 1382.0, 1390.0]
    polished = polish_early_cuts_to_silence_ends(
        cuts,
        silence_ends=silence_ends,
        duration_sec=4000.0,
        min_early_sec=12.0,
        max_early_sec=55.0,
        already_near_sec=5.0,
        confirm_times=[644.0, 1383.0],
        confirm_within_sec=8.0,
    )
    assert polished[1] == 643.0
    assert polished[2] == 1382.0


def test_polish_early_cuts_skips_when_already_near_speech_onset():
    # LKE-shaped: cut already at a transition (near confirmed silence) — do not yank.
    cuts = [0.0, 1044.0, 2000.0]
    silence_ends = [1040.0, 1060.0, 1070.0, 1080.0]
    polished = polish_early_cuts_to_silence_ends(
        cuts,
        silence_ends=silence_ends,
        duration_sec=2000.0,
        speech_onsets=[1045.0],
        confirm_times=[1041.0, 1061.0, 1071.0],
        already_near_sec=5.0,
    )
    assert polished[1] == 1044.0


def test_polish_early_cuts_ignores_unconfirmed_far_silence_blips():
    # Last silence in window is a breath/rest with no confirm; earlier silence
    # has confirm — must not overshoot to the far blip.
    cuts = [0.0, 100.0, 500.0]
    silence_ends = [115.0, 130.0, 138.0]
    confirm_times = [116.0]  # only confirms 115
    polished = polish_early_cuts_to_silence_ends(
        cuts,
        silence_ends=silence_ends,
        duration_sec=500.0,
        min_early_sec=12.0,
        max_early_sec=40.0,
        confirm_times=confirm_times,
        confirm_within_sec=8.0,
    )
    assert polished[1] == 115.0


def test_polish_early_cuts_leaves_cut_without_confirmed_forward_silence():
    cuts = [0.0, 100.0, 500.0]
    silence_ends = [50.0, 140.0, 200.0]  # 140 is >25s ahead → no short fallback
    polished = polish_early_cuts_to_silence_ends(
        cuts,
        silence_ends=silence_ends,
        duration_sec=500.0,
        min_early_sec=12.0,
        max_early_sec=40.0,
        confirm_times=[999.0],  # non-empty pool, nothing matches window
        confirm_within_sec=8.0,
    )
    assert polished[1] == 100.0


def test_polish_early_cuts_short_range_fallback_without_confirm_match():
    cuts = [0.0, 100.0, 500.0]
    silence_ends = [50.0, 118.0, 200.0]
    polished = polish_early_cuts_to_silence_ends(
        cuts,
        silence_ends=silence_ends,
        duration_sec=500.0,
        min_early_sec=12.0,
        max_early_sec=40.0,
        confirm_times=[999.0],
        confirm_within_sec=8.0,
    )
    assert polished[1] == 118.0
