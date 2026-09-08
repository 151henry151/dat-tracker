"""Render Jon King–style show.txt files."""

from __future__ import annotations

from datetime import date
from typing import Any


def _human_date(iso_date: str) -> str:
    d = date.fromisoformat(iso_date)
    return f"{d.strftime('%B')} {d.day}, {d.year}"


def format_show_txt(
    *,
    artist: str,
    date: str,
    venue: str | None = None,
    city: str | None = None,
    state: str | None = None,
    source: str | None = None,
    transfer: str | None = None,
    transferer: str = "Cate Crowe",
    tracker: str,
    set_label: str = "One Set",
    tracks: list[dict[str, Any]] | None = None,
) -> str:
    lines: list[str] = [
        artist,
        f"{_human_date(date)} ({date})",
    ]
    if venue:
        lines.append(venue)
    location = ", ".join(p for p in (city, state) if p)
    if location:
        lines.append(location)
    lines.append("")
    if source:
        lines.append(f"Source: {source}")
    if transfer:
        lines.append(f"Transfer: {transfer}")
    lines.append(f"Transferred by: {transferer}")
    lines.append(f"Tracked & Uploaded by: {tracker}")
    lines.append("")
    lines.append(f"{set_label}:")
    for track in tracks or []:
        lines.append(f"{track['num']}. {track['title']}")
    lines.append("")
    return "\n".join(lines)
