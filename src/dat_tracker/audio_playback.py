"""Audio playback helpers for the review TUI (PortAudio via sounddevice)."""

from __future__ import annotations

import subprocess
import tempfile
import threading
from pathlib import Path
from typing import Any

import numpy as np


def clamp_play_range(
    start_sec: float,
    end_sec: float,
    *,
    duration_sec: float,
) -> tuple[float, float]:
    start = max(0.0, min(float(duration_sec), float(start_sec)))
    end = max(0.0, min(float(duration_sec), float(end_sec)))
    if end <= start:
        end = min(float(duration_sec), start + 0.01)
    return start, end


def loop_window_around_cut(
    cut_sec: float,
    *,
    duration_sec: float,
    half_window_sec: float = 8.0,
) -> tuple[float, float]:
    half = max(0.1, float(half_window_sec))
    return clamp_play_range(
        float(cut_sec) - half,
        float(cut_sec) + half,
        duration_sec=float(duration_sec),
    )


def decode_pcm_segment(
    audio_path: Path,
    *,
    start_sec: float,
    end_sec: float,
    sample_rate: int = 44100,
) -> tuple[np.ndarray, int]:
    """Return mono float32 samples for [start_sec, end_sec) and sample_rate."""
    start_sec, end_sec = clamp_play_range(
        start_sec, end_sec, duration_sec=max(end_sec, start_sec + 0.01)
    )
    duration = max(0.01, end_sec - start_sec)
    with tempfile.NamedTemporaryFile(suffix=".f32", delete=False) as tmp:
        raw_path = Path(tmp.name)
    try:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-ss",
                f"{start_sec:.3f}",
                "-t",
                f"{duration:.3f}",
                "-i",
                str(audio_path),
                "-ac",
                "1",
                "-ar",
                str(sample_rate),
                "-f",
                "f32le",
                str(raw_path),
            ],
            check=True,
            capture_output=True,
        )
        samples = np.fromfile(raw_path, dtype="<f4")
    finally:
        raw_path.unlink(missing_ok=True)
    return samples, sample_rate


class AudioPlayer:
    """Simple one-shot / looping player; safe no-op if sounddevice missing."""

    def __init__(self) -> None:
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._playing = False
        self.position_sec = 0.0
        self._lock = threading.Lock()

    @property
    def is_playing(self) -> bool:
        return self._playing

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._thread = None
        self._playing = False

    def play_segment(
        self,
        audio_path: Path,
        *,
        start_sec: float,
        end_sec: float,
        loop: bool = False,
        sample_rate: int = 44100,
    ) -> None:
        self.stop()
        self._stop = threading.Event()
        samples, sr = decode_pcm_segment(
            Path(audio_path),
            start_sec=start_sec,
            end_sec=end_sec,
            sample_rate=sample_rate,
        )
        if samples.size == 0:
            return

        def _run() -> None:
            try:
                import sounddevice as sd
            except ImportError:
                self._playing = False
                return
            self._playing = True
            try:
                while not self._stop.is_set():
                    with self._lock:
                        self.position_sec = float(start_sec)
                    sd.play(samples, sr, blocking=True)
                    if not loop or self._stop.is_set():
                        break
            finally:
                try:
                    import sounddevice as sd

                    sd.stop()
                except Exception:
                    pass
                self._playing = False

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()
