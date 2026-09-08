"""Tests for aligning a ground-truth show inside a longer raw FLAC."""

from dat_tracker.align import best_offset_sec, pcm_energy, sliding_energy_distance


def test_pcm_energy_empty():
    assert pcm_energy(b"") == []


def test_pcm_energy_constant_block():
    # Two int16 samples of 1000, then two of 0 (little-endian)
    pcm = (1000).to_bytes(2, "little", signed=True) * 2 + (0).to_bytes(2, "little", signed=True) * 2
    energy = pcm_energy(pcm, hop=2)
    assert len(energy) == 2
    assert energy[0] > energy[1]


def test_sliding_energy_distance_finds_embedded_pattern():
    # Synthetic energies: needle matches haystack starting at index 3
    hay = [1.0, 2.0, 3.0, 10.0, 11.0, 12.0, 4.0]
    needle = [10.0, 11.0, 12.0]
    idx, dist = sliding_energy_distance(hay, needle)
    assert idx == 3
    assert dist == 0.0


def test_best_offset_sec_converts_hop_index():
    hay = [0.0] * 10 + [5.0, 6.0, 7.0] + [0.0] * 5
    needle = [5.0, 6.0, 7.0]
    offset, dist = best_offset_sec(hay, needle, sample_rate=100, hop=10)
    # index 10 → 10 * hop / rate = 1.0s
    assert offset == 1.0
    assert dist == 0.0
