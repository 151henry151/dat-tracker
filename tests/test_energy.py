"""Tests for energy / novelty-based boundary proposals."""

from dat_tracker.energy import (
    frame_rms_from_pcm,
    novelty_from_rms,
    peaks_from_novelty,
    propose_cuts_from_rms,
)


def _pcm_sine_block(n_samples: int, amplitude: int = 10000) -> bytes:
    # Constant high "energy" block of identical samples (RMS proxy).
    return (amplitude).to_bytes(2, "little", signed=True) * n_samples


def test_frame_rms_from_pcm_empty():
    assert frame_rms_from_pcm(b"") == []


def test_frame_rms_from_pcm_detects_quiet_then_loud():
    quiet = _pcm_sine_block(4, amplitude=0)
    loud = _pcm_sine_block(4, amplitude=10000)
    rms = frame_rms_from_pcm(quiet + loud, hop=4)
    assert len(rms) == 2
    assert rms[0] < rms[1]


def test_novelty_from_rms_peaks_at_jump():
    rms = [1.0, 1.0, 1.0, 10.0, 10.0, 10.0]
    nov = novelty_from_rms(rms)
    assert nov[0] == 0.0
    assert nov[3] == max(nov)


def test_peaks_from_novelty_respects_threshold_and_refractory():
    nov = [0.0, 0.1, 5.0, 4.5, 0.2, 0.1, 6.0, 0.0]
    peaks = peaks_from_novelty(nov, threshold=1.0, min_separation=2)
    assert peaks == [2, 6]


def test_propose_cuts_from_rms_includes_endpoints_and_peaks():
    # Jump at frame 3 and frame 8
    rms = [1.0] * 3 + [20.0] * 5 + [1.0] * 5
    cuts = propose_cuts_from_rms(
        rms,
        sample_rate=1000,
        hop=1000,
        novelty_threshold=5.0,
        min_separation_sec=1.0,
    )
    assert cuts[0] == 0.0
    assert cuts[-1] == 13.0  # 13 frames * 1s
    assert 3.0 in cuts
