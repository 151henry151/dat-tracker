"""Tests for playback window helpers and ffplay command building."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from dat_tracker.audio_playback import (
    AudioPlayer,
    clamp_play_range,
    ffplay_segment_command,
    loop_window_around_cut,
)


def test_loop_window_around_cut_centers_with_padding():
    start, end = loop_window_around_cut(
        cut_sec=50.0,
        duration_sec=100.0,
        half_window_sec=8.0,
    )
    assert start == pytest.approx(42.0)
    assert end == pytest.approx(58.0)


def test_loop_window_clamps_at_show_edges():
    start, end = loop_window_around_cut(
        cut_sec=2.0,
        duration_sec=100.0,
        half_window_sec=8.0,
    )
    assert start == 0.0
    assert end == pytest.approx(10.0)

    start, end = loop_window_around_cut(
        cut_sec=98.0,
        duration_sec=100.0,
        half_window_sec=8.0,
    )
    assert start == pytest.approx(90.0)
    assert end == 100.0


def test_playhead_for_cut_defaults_to_loop_window_start():
    from dat_tracker.audio_playback import playhead_for_cut

    assert playhead_for_cut(50.0, duration_sec=100.0) == pytest.approx(42.0)
    assert playhead_for_cut(2.0, duration_sec=100.0) == 0.0


def test_resolve_playback_start_sec():
    from dat_tracker.audio_playback import resolve_playback_start_sec

    assert resolve_playback_start_sec(42.5, selected_cut_sec=10.0, duration_sec=100.0) == 42.5
    assert resolve_playback_start_sec(None, selected_cut_sec=10.0, duration_sec=100.0) == 10.0
    assert resolve_playback_start_sec(None, selected_cut_sec=None, duration_sec=100.0) == 0.0
    assert resolve_playback_start_sec(150.0, selected_cut_sec=0.0, duration_sec=100.0) == 100.0
    assert resolve_playback_start_sec(-5.0, selected_cut_sec=0.0, duration_sec=100.0) == 0.0


def test_clamp_play_range():
    assert clamp_play_range(-1.0, 5.0, duration_sec=10.0) == (0.0, 5.0)
    assert clamp_play_range(8.0, 12.0, duration_sec=10.0) == (8.0, 10.0)
    assert clamp_play_range(5.0, 5.0, duration_sec=10.0) == (5.0, 5.01)


def test_ffplay_segment_command_shape():
    cmd = ffplay_segment_command(
        Path("/tmp/show.flac"),
        start_sec=12.5,
        end_sec=20.5,
    )
    assert cmd[0] == "ffplay"
    assert "-nodisp" in cmd
    assert "-autoexit" in cmd
    assert cmd[cmd.index("-ss") + 1] == "12.500"
    assert cmd[cmd.index("-t") + 1] == "8.000"
    assert cmd[-1] == "/tmp/show.flac"


def test_estimate_playback_position_one_shot_and_loop():
    from dat_tracker.audio_playback import estimate_playback_position

    assert estimate_playback_position(
        10.0, 20.0, elapsed_sec=3.0, loop=False
    ) == pytest.approx(13.0)
    assert estimate_playback_position(
        10.0, 20.0, elapsed_sec=15.0, loop=False
    ) == pytest.approx(20.0)
    assert estimate_playback_position(
        10.0, 20.0, elapsed_sec=12.0, loop=True
    ) == pytest.approx(12.0)
    assert estimate_playback_position(
        10.0, 20.0, elapsed_sec=0.0, loop=True
    ) == pytest.approx(10.0)


def test_audio_player_uses_ffplay_subprocess():
    player = AudioPlayer()
    fake_proc = MagicMock()
    fake_proc.poll.side_effect = [None, None, 0]
    fake_proc.returncode = 0
    fake_proc.stderr = None
    fake_proc.wait.return_value = 0
    with patch("dat_tracker.audio_playback.shutil.which", return_value="/usr/bin/ffplay"):
        with patch(
            "dat_tracker.audio_playback.subprocess.Popen", return_value=fake_proc
        ) as popen:
            player.play_segment(
                Path("/tmp/show.flac"),
                start_sec=1.0,
                end_sec=2.0,
                loop=False,
            )
            assert player._thread is not None
            player._thread.join(timeout=2.0)
    assert popen.called
    cmd = popen.call_args[0][0]
    assert cmd[0] == "ffplay"
    assert player.last_error is None
