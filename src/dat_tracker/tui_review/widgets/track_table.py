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
