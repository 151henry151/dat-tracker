"""Tests for RMS-rise confirmation of silence ends."""

from pathlib import Path

from dat_tracker.energy import (
    extract_mono_pcm,
    frame_rms_from_pcm,
    silence_ends_with_rms_rise,
)


def test_silence_ends_with_rms_rise_keeps_onset_after_quiet(tmp_path: Path):
    # Build synthetic PCM via writing frames: 5s quiet then 5s loud.
    import subprocess

    src = tmp_path / "q_then_loud.flac"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "aevalsrc=0:d=5",
            "-f",
            "lavfi",
            "-i",
            "sine=f=440:d=5",
            "-filter_complex",
            "[0][1]concat=n=2:v=0:a=1",
            str(src),
        ],
        check=True,
        capture_output=True,
    )
    # Silence end at ~5.0 should show rise; a mid-loud "silence" at 7.0 should not.
    kept = silence_ends_with_rms_rise(src, [5.0, 7.0])
    assert 5.0 in kept
    assert 7.0 not in kept
