"""Merge raw Dropbox candidates with Archive.org already-uploaded rows."""

from __future__ import annotations

from typing import Any


def _match_key(show: dict[str, Any]) -> tuple[str, str, str]:
    return (
        (show.get("collection") or "").lower(),
        (show.get("date") or ""),
        (show.get("id") or "").lower(),
    )


def _artist_date_key(show: dict[str, Any]) -> tuple[str, str, str]:
    return (
        (show.get("collection") or "").lower(),
        (show.get("date") or ""),
        (show.get("artist") or "").strip().lower(),
    )


def merge_catalog(
    *,
    raw_shows: list[dict[str, Any]],
    ia_shows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Prefer IA metadata when a raw dump show matches an uploaded item."""
    ia_by_id = {_match_key(s): s for s in ia_shows}
    ia_by_artist_date = {
        _artist_date_key(s): s for s in ia_shows if s.get("artist")
    }
    used_ia: set[tuple[str, str, str]] = set()
    merged: list[dict[str, Any]] = []

    for raw in raw_shows:
        ia = ia_by_id.get(_match_key(raw))
        if ia is None and raw.get("artist"):
            ia = ia_by_artist_date.get(_artist_date_key(raw))
        if ia is None:
            merged.append(dict(raw))
            continue
        used_ia.add(_match_key(ia))
        row = dict(raw)
        row.update(
            {
                "id": ia["id"],
                "artist": ia.get("artist") or raw.get("artist") or "",
                "date": ia.get("date") or raw.get("date") or "",
                "venue": ia.get("venue") if ia.get("venue") is not None else raw.get("venue"),
                "city": ia.get("city") if ia.get("city") is not None else raw.get("city"),
                "state": ia.get("state") if ia.get("state") is not None else raw.get("state"),
                "collection": ia["collection"],
                "status": "already_uploaded",
                "ia_identifier": ia.get("ia_identifier"),
                "ia_collection": ia.get("ia_collection"),
                "source": ia.get("source") if ia.get("source") is not None else raw.get("source"),
                "notes": ia.get("notes") if ia.get("notes") is not None else raw.get("notes"),
                "raw_path": raw.get("raw_path") or ia.get("raw_path") or "",
            }
        )
        merged.append(row)

    for ia in ia_shows:
        if _match_key(ia) not in used_ia:
            merged.append(dict(ia))

    merged.sort(key=lambda s: (s.get("date") or "", s.get("id") or ""))
    return merged
