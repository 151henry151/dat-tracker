"""Audio playback helpers for the review TUI.

Primary path uses ``ffplay`` (ships with ffmpeg) so PortAudio/sounddevice
device selection does not silently play to HDMI or fail in a worker thread.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import threading
import time
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


def resolve_playback_start_sec(
    playhead_sec: float | None,
    *,
    selected_cut_sec: float | None = None,
    duration_sec: float,
) -> float:
    """Pick where Space should start: explicit playhead, else selected cut, else 0."""
    duration = max(0.0, float(duration_sec))
    if playhead_sec is not None:
        return max(0.0, min(duration, float(playhead_sec)))
    if selected_cut_sec is not None:
        return max(0.0, min(duration, float(selected_cut_sec)))
    return 0.0


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


def playhead_for_cut(
    cut_sec: float,
    *,
    duration_sec: float,
    half_window_sec: float = 8.0,
) -> float:
    """Default cyan playhead when selecting a cut (start of the loop window)."""
    start, _end = loop_window_around_cut(
        cut_sec, duration_sec=duration_sec, half_window_sec=half_window_sec
    )
    return start


def estimate_playback_position(
    start_sec: float,
    end_sec: float,
    *,
    elapsed_sec: float,
    loop: bool,
) -> float:
    """Map wall-clock elapsed time onto the hearing window."""
    start = float(start_sec)
    end = float(end_sec)
    dur = max(0.01, end - start)
    elapsed = max(0.0, float(elapsed_sec))
    if loop:
        return start + (elapsed % dur)
    return min(end, start + elapsed)


def ffplay_segment_command(
    audio_path: Path,
    *,
    start_sec: float,
    end_sec: float,
) -> list[str]:
    """Build an ``ffplay`` argv that plays ``[start_sec, end_sec)`` once."""
    start_sec, end_sec = clamp_play_range(
        start_sec, end_sec, duration_sec=max(end_sec, start_sec + 0.01)
    )
    duration = max(0.01, end_sec - start_sec)
    return [
        "ffplay",
        "-nodisp",
        "-autoexit",
        "-loglevel",
        "error",
        "-volume",
        "100",
        "-ss",
        f"{start_sec:.3f}",
        "-t",
        f"{duration:.3f}",
        str(audio_path),
    ]


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
    """Segment / loop player via ffplay; sounddevice is a last-resort fallback."""

    def __init__(self) -> None:
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._playing = False
        self._proc: subprocess.Popen[Any] | None = None
        self.position_sec = 0.0
        self.last_error: str | None = None
        self._lock = threading.Lock()
        self._seg_start = 0.0
        self._seg_end = 0.0
        self._loop = False
        self._loop_mono_start: float | None = None

    @property
    def is_playing(self) -> bool:
        return self._playing

    @property
    def hearing_window(self) -> tuple[float, float] | None:
        if not self._playing:
            return None
        with self._lock:
            return (self._seg_start, self._seg_end)

    @property
    def is_looping(self) -> bool:
        with self._lock:
            return bool(self._loop) and self._playing

    def current_position_sec(self) -> float | None:
        """Estimated show time currently audible (wall-clock vs segment)."""
        if not self._playing:
            return None
        with self._lock:
            start = self._seg_start
            end = self._seg_end
            loop = self._loop
            t0 = self._loop_mono_start
        if t0 is None:
            return start
        pos = estimate_playback_position(
            start, end, elapsed_sec=time.monotonic() - t0, loop=loop
        )
        self.position_sec = pos
        return pos

    def stop(self) -> None:
        self._stop.set()
        with self._lock:
            proc = self._proc
            self._proc = None
            self._loop_mono_start = None
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                proc.kill()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._thread = None
        self._playing = False
        try:
            import sounddevice as sd

            sd.stop()
        except Exception:
            pass

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
        self.last_error = None
        audio_path = Path(audio_path)
        start_sec, end_sec = clamp_play_range(
            start_sec, end_sec, duration_sec=max(end_sec, start_sec + 0.01)
        )
        with self._lock:
            self._seg_start = start_sec
            self._seg_end = end_sec
            self._loop = bool(loop)
            self._loop_mono_start = time.monotonic()
            self.position_sec = start_sec

        def _run() -> None:
            self._playing = True
            try:
                if shutil.which("ffplay"):
                    self._run_ffplay(audio_path, start_sec, end_sec, loop=loop)
                else:
                    self._run_sounddevice(
                        audio_path,
                        start_sec,
                        end_sec,
                        loop=loop,
                        sample_rate=sample_rate,
                    )
            except Exception as exc:  # noqa: BLE001 — surface to TUI status
                self.last_error = str(exc)
            finally:
                self._playing = False
                with self._lock:
                    self._proc = None
                    self._loop_mono_start = None

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()

    def _mark_loop_iteration(self, start_sec: float) -> None:
        with self._lock:
            self._loop_mono_start = time.monotonic()
            self.position_sec = float(start_sec)

    def _run_ffplay(
        self,
        audio_path: Path,
        start_sec: float,
        end_sec: float,
        *,
        loop: bool,
    ) -> None:
        cmd = ffplay_segment_command(
            audio_path, start_sec=start_sec, end_sec=end_sec
        )
        while not self._stop.is_set():
            self._mark_loop_iteration(start_sec)
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
            with self._lock:
                self._proc = proc
            while proc.poll() is None:
                if self._stop.wait(0.05):
                    proc.terminate()
                    try:
                        proc.wait(timeout=1.0)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                    return
            if proc.returncode not in (0, None) and not self._stop.is_set():
                err = ""
                if proc.stderr is not None:
                    err = proc.stderr.read().decode(errors="replace").strip()
                self.last_error = err or f"ffplay exited {proc.returncode}"
                return
            if not loop or self._stop.is_set():
                return

    def _run_sounddevice(
        self,
        audio_path: Path,
        start_sec: float,
        end_sec: float,
        *,
        loop: bool,
        sample_rate: int,
    ) -> None:
        try:
            import sounddevice as sd
        except ImportError as exc:
            self.last_error = (
                "ffplay not found and sounddevice is not installed "
                f"({exc})"
            )
            return
        samples, sr = decode_pcm_segment(
            audio_path,
            start_sec=start_sec,
            end_sec=end_sec,
            sample_rate=sample_rate,
        )
        if samples.size == 0:
            self.last_error = "Decoded empty audio segment"
            return
        while not self._stop.is_set():
            self._mark_loop_iteration(start_sec)
            sd.play(samples, sr, blocking=True)
            if not loop or self._stop.is_set():
                break
        try:
            sd.stop()
        except Exception:
            pass
