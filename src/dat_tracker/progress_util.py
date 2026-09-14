"""Helpers for live progress reporting during long pipeline stages."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager

ProgressCb = Callable[[str, float], None]


def emit_progress(
    on_progress: ProgressCb | None,
    message: str,
    fraction: float,
) -> None:
    if on_progress is None:
        return
    on_progress(message, max(0.0, min(1.0, float(fraction))))


def map_stage(
    on_progress: ProgressCb | None,
    *,
    start: float,
    end: float,
) -> ProgressCb | None:
    """Return a callback that maps local 0..1 into overall ``start``..``end``."""
    if on_progress is None:
        return None

    def mapped(message: str, local: float) -> None:
        overall = start + (end - start) * max(0.0, min(1.0, float(local)))
        on_progress(message, overall)

    return mapped


@contextmanager
def progress_heartbeat(
    on_progress: ProgressCb | None,
    message: str,
    *,
    fraction: float,
    interval_sec: float = 2.0,
) -> Iterator[None]:
    """Keep the UI alive during a blocking call that has no finer progress.

    Re-emits ``message`` with elapsed seconds at ``fraction`` until the
    context exits.
    """
    if on_progress is None:
        yield
        return

    stop = threading.Event()
    started = time.monotonic()

    def _pulse() -> None:
        while not stop.wait(interval_sec):
            elapsed = int(time.monotonic() - started)
            mins, secs = divmod(elapsed, 60)
            on_progress(
                f"{message} ({mins}m {secs:02d}s elapsed — still working)…",
                fraction,
            )

    on_progress(f"{message}…", fraction)
    thread = threading.Thread(target=_pulse, name="progress-heartbeat", daemon=True)
    thread.start()
    try:
        yield
    finally:
        stop.set()
        thread.join(timeout=interval_sec + 1.0)
