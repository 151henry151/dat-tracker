"""Tests for Whisper transcription progress callbacks."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from dat_tracker.speech import transcribe_faster_whisper
from dat_tracker.track_show import ensure_whisper_cache


def test_transcribe_faster_whisper_emits_segment_progress(tmp_path: Path):
    audio = tmp_path / "a.flac"
    audio.write_bytes(b"f")
    events: list[tuple[str, float]] = []

    class FakeSeg:
        def __init__(self, start: float, end: float, text: str):
            self.start = start
            self.end = end
            self.text = text

    fake_model = MagicMock()
    fake_model.transcribe.return_value = (
        iter(
            [
                FakeSeg(0.0, 10.0, "a"),
                FakeSeg(10.0, 50.0, "b"),
                FakeSeg(50.0, 100.0, "c"),
            ]
        ),
        SimpleNamespace(duration=100.0),
    )

    with patch("faster_whisper.WhisperModel", return_value=fake_model):
        payload = transcribe_faster_whisper(
            audio,
            on_progress=lambda m, f: events.append((m, f)),
        )

    assert len(payload["segments"]) == 3
    assert any("model" in m.lower() for m, _ in events)
    assert any("transcrib" in m.lower() for m, _ in events)
    fracs = [f for _, f in events]
    assert fracs[-1] >= fracs[0]
    assert max(fracs) <= 1.0


def test_ensure_whisper_cache_forwards_progress(tmp_path: Path):
    audio = tmp_path / "a.flac"
    audio.write_bytes(b"f")
    cache = tmp_path / "whisper_segments.json"
    seen: list[tuple[str, float]] = []

    with patch(
        "dat_tracker.track_show.transcribe_faster_whisper",
        return_value={"segments": []},
    ) as mock_tx:
        ensure_whisper_cache(
            audio_path=audio,
            cache_path=cache,
            on_progress=lambda m, f: seen.append((m, f)),
        )
        assert mock_tx.call_args.kwargs.get("on_progress") is not None
