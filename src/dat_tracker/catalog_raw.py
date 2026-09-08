"""Infer candidate shows from Dropbox dump paths / unzip listings."""

from __future__ import annotations

import re
from pathlib import PurePosixPath
from typing import Any

DATE_RE = re.compile(r"(?P<date>\d{4}-\d{2}-\d{2})")
ETREE_ID_RE = re.compile(
    r"(?P<id>[A-Za-z0-9]+(?:\.[A-Za-z0-9]+)?\d{4}-\d{2}-\d{2}(?:\.[A-Za-z0-9]+)?)"
)
ZIP_LISTING_RE = re.compile(
    r"^\s*\d+\s+\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}\s+(?P<path>.+)$"
)


def infer_collection_from_path(path: str) -> str | None:
    lower = path.lower().replace("\\", "/")
    if "dave w" in lower:
        return "Dave Ward Collection"
    if "brian h" in lower:
        return "Brian H Collection"
    return None


def parse_zip_listing_line(line: str) -> str | None:
    match = ZIP_LISTING_RE.match(line.rstrip("\n"))
    if not match:
        return None
    return match.group("path").strip()


def _guess_id_and_date(filename: str) -> tuple[str | None, str | None]:
    stem = PurePosixPath(filename).stem
    compact = stem.replace(" ", "")
    etree = ETREE_ID_RE.search(compact)
    date_match = DATE_RE.search(stem)
    date = date_match.group("date") if date_match else None
    if etree:
        show_id = etree.group("id")
        if date is None:
            date = DATE_RE.search(show_id).group("date")  # type: ignore[union-attr]
        return show_id, date
    if date:
        slug = re.sub(r"[^A-Za-z0-9._-]+", "", compact)
        return slug or None, date
    return None, None


def _guess_artist(filename: str, show_id: str | None, date: str | None) -> str:
    stem = PurePosixPath(filename).stem
    compact = stem.replace(" ", "")
    if show_id and compact == show_id:
        return ""
    artist = stem
    if date:
        artist = artist.replace(date, "")
    artist = re.sub(r"[_\-]+", " ", artist).strip(" -_")
    return artist


def path_to_show(path: str) -> dict[str, Any] | None:
    normalized = path.replace("\\", "/").lstrip("./")
    if not normalized.lower().endswith(".flac"):
        return None
    collection = infer_collection_from_path(normalized)
    if collection is None:
        return None
    name = PurePosixPath(normalized).name
    show_id, date = _guess_id_and_date(name)
    if not show_id or not date:
        return None
    return {
        "id": show_id,
        "raw_path": normalized,
        "artist": _guess_artist(name, show_id, date),
        "date": date,
        "venue": None,
        "city": None,
        "state": None,
        "collection": collection,
        "status": "todo",
        "ia_identifier": None,
        "ia_collection": None,
        "source": None,
        "notes": None,
    }


def shows_from_zip_paths(paths: list[str]) -> list[dict[str, Any]]:
    shows: list[dict[str, Any]] = []
    for path in paths:
        show = path_to_show(path)
        if show is not None:
            shows.append(show)
    return shows
