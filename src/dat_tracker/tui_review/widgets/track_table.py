"""Track list widget helpers."""

from __future__ import annotations

from typing import Any


def format_track_rows(plan: dict[str, Any]) -> list[tuple[str, str, str, str, str]]:
    """Return rows: index, type, title, segue, duration."""
    rows: list[tuple[str, str, str, str, str]] = []
    for track in sorted(plan.get("tracks") or [], key=lambda t: int(t["index"])):
        dur = float(track["end_sec"]) - float(track["start_sec"])
        title = track.get("title") or ""
        segue = ">" if track.get("segue_into_next") else ""
        rows.append(
            (
                str(track["index"]),
                str(track.get("track_type") or "unknown"),
                str(title),
                segue,
                f"{dur:.1f}s",
            )
        )
    return rows


def resolve_track_row_selection(
    tracks: list[dict[str, Any]],
    cuts_sec: list[float],
    cursor_row: int,
) -> tuple[int, float] | None:
    """Map a track-table row to ``(cut_index, playhead_sec)`` at track start.

    Tracks are assumed sorted by index (same order as :func:`format_track_rows`).
    """
    if cursor_row < 0 or cursor_row >= len(tracks) or not cuts_sec:
        return None
    start = float(tracks[cursor_row]["start_sec"])
    cut_index = min(
        range(len(cuts_sec)), key=lambda i: abs(float(cuts_sec[i]) - start)
    )
    return int(cut_index), start
