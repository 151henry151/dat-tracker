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
# Live Bluegrass dump: YYMMDD_... or YYYYMMDD_... / YYYYMMDD-...
DUMP_DATE_RE = re.compile(
    r"^(?:(?P<ymd>\d{8})|(?P<yymd>\d{6}))(?P<rest>[_\-].*)$"
)
PART_SUFFIX_RE = re.compile(
    r"(?i)(?:^|[_\-])(?:part)?(?P<part>\d+|I{1,3}|IV)(?:$|[_\-])"
)

# Filename tokens → (etree abbrev, display artist). Longer keys first via sorted match.
ABBREV_MAP: dict[str, tuple[str, str]] = {
    "del_mccoury_band": ("del", "Del McCoury Band"),
    "old_crow_medicine_show": ("ocms", "Old Crow Medicine Show"),
    "railroad_earth": ("rre", "Railroad Earth"),
    "crooked_still": ("crookedstill", "Crooked Still"),
    "jeff_mandela_proj": ("jmp", "Jeff Mandell Project"),
    "little_feat": ("lf", "Little Feat"),
    "hot_rory": ("hotrize", "Hot Rize"),
    "hot_rize": ("hotrize", "Hot Rize"),
    "string_cheese": ("sci", "String Cheese Incident"),
    "yonder": ("ymsb", "Yonder Mountain String Band"),
    "watson": ("docwatson", "Doc Watson"),
    "jcb": ("jcb", "John Cowan"),
    "los": ("los", "Leftover Salmon"),
    "sci": ("sci", "String Cheese Incident"),
    "ymsb": ("ymsb", "Yonder Mountain String Band"),
    "del": ("del", "Del McCoury Band"),
    "ocms": ("ocms", "Old Crow Medicine Show"),
    "rre": ("rre", "Railroad Earth"),
    "lf": ("lf", "Little Feat"),
    "jmp": ("jmp", "Jeff Mandell Project"),
}


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


def _expand_yymmdd(yymd: str) -> str | None:
    """Convert YYMMDD to YYYY-MM-DD. Returns None if day/month invalid or XX day."""
    if len(yymd) != 6 or not yymd.isdigit():
        return None
    yy, mm, dd = int(yymd[:2]), int(yymd[2:4]), int(yymd[4:6])
    if mm < 1 or mm > 12 or dd < 1 or dd > 31:
        return None
    year = 1900 + yy if yy >= 70 else 2000 + yy
    return f"{year:04d}-{mm:02d}-{dd:02d}"


def _expand_yyyymmdd(ymd: str) -> str | None:
    if len(ymd) != 8 or not ymd.isdigit():
        return None
    year, mm, dd = int(ymd[:4]), int(ymd[4:6]), int(ymd[6:8])
    if year < 1900 or mm < 1 or mm > 12 or dd < 1 or dd > 31:
        return None
    return f"{year:04d}-{mm:02d}-{dd:02d}"


def _strip_part_suffix(label: str) -> str:
    """Remove trailing multipart markers like _1, _2, _I, _II from a label."""
    cleaned = re.sub(r"(?i)[_\-](?:part)?(?:\d+|I{1,3}|IV)$", "", label)
    return cleaned.strip("_- ")


def _match_abbrev(label: str) -> tuple[str, str] | None:
    """Return (etree_abbrev, artist) from a filename label after the date."""
    normalized = label.lower().replace("-", "_")
    normalized = re.sub(r"[^a-z0-9_]+", "_", normalized)
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    # Prefer longer / more specific keys.
    for key in sorted(ABBREV_MAP.keys(), key=len, reverse=True):
        if (
            normalized == key
            or normalized.startswith(key + "_")
            or f"_{key}_" in f"_{normalized}_"
        ):
            return ABBREV_MAP[key]
    return None


def _guess_id_and_date(filename: str) -> tuple[str | None, str | None, str]:
    """Return (show_id, iso_date, artist_guess)."""
    stem = PurePosixPath(filename).stem
    compact = stem.replace(" ", "")

    # Prefer dump-style leading dates.
    dump = DUMP_DATE_RE.match(stem)
    if dump:
        if dump.group("ymd"):
            date = _expand_yyyymmdd(dump.group("ymd"))
        else:
            date = _expand_yymmdd(dump.group("yymd"))
        rest = dump.group("rest").lstrip("_-")
        label = _strip_part_suffix(rest)
        mapped = _match_abbrev(label)
        if date and mapped:
            abbrev, artist = mapped
            # Source-ish suffixes after known abbrev (SBD, Matrix, RR, AUD, FM).
            source_suffix = ""
            lower_label = label.lower()
            for token in ("sbd", "matrix", "aud", "fm", "master"):
                if re.search(rf"(?i)(^|[_\-]){token}($|[_\-])", lower_label):
                    source_suffix = f".{token.upper()}" if token in {"sbd", "matrix"} else ""
                    if token == "matrix":
                        source_suffix = ".Matrix"
                    elif token == "sbd":
                        source_suffix = ".SBD"
                    break
            # YMSB Sbd/Aud in festival names: 20030418-OSMF-YMSB-Sbd
            if re.search(r"(?i)ymsb.*sbd|sbd.*ymsb", lower_label):
                source_suffix = ".SBD"
            elif re.search(r"(?i)ymsb.*aud|aud.*ymsb", lower_label):
                source_suffix = ".Matrix" if "matrix" in lower_label else ""
                # IA uses ymsb2003-04-18.Matrix and .SBD — Aud maps separately if needed
                if re.search(r"(?i)\baud\b|_aud|aud\.|-aud", lower_label) and "sbd" not in lower_label:
                    # Keep base id without suffix for AUD unless we know Matrix; leave plain
                    source_suffix = ""
            show_id = f"{abbrev}{date}{source_suffix}"
            return show_id, date, artist
        if date:
            slug = re.sub(r"[^A-Za-z0-9._-]+", "", compact)
            artist = _guess_artist_from_label(label)
            return slug or None, date, artist

    etree = ETREE_ID_RE.search(compact)
    date_match = DATE_RE.search(stem)
    date = date_match.group("date") if date_match else None
    if etree:
        show_id = etree.group("id")
        if date is None:
            date = DATE_RE.search(show_id).group("date")  # type: ignore[union-attr]
        artist = _guess_artist(filename, show_id, date)
        mapped = _match_abbrev(show_id)
        if mapped:
            artist = mapped[1]
        return show_id, date, artist
    if date:
        slug = re.sub(r"[^A-Za-z0-9._-]+", "", compact)
        return slug or None, date, _guess_artist(filename, slug, date)
    return None, None, ""


def _guess_artist_from_label(label: str) -> str:
    mapped = _match_abbrev(label)
    if mapped:
        return mapped[1]
    cleaned = _strip_part_suffix(label)
    cleaned = re.sub(r"[_\-]+", " ", cleaned).strip()
    return cleaned


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
    show_id, date, artist = _guess_id_and_date(name)
    if not show_id or not date:
        return None
    return {
        "id": show_id,
        "raw_path": normalized,
        "artist": artist,
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


def _coalesce_key(show: dict[str, Any]) -> tuple[str, str, str]:
    """Coalesce multipart discs of the same id; keep SBD/Matrix ids distinct."""
    return (
        show["collection"],
        show["date"],
        show["id"].lower(),
    )


def shows_from_zip_paths(paths: list[str]) -> list[dict[str, Any]]:
    """Build show rows from zip paths; coalesce multipart FLACs for one show."""
    by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    order: list[tuple[str, str, str]] = []
    for path in paths:
        show = path_to_show(path)
        if show is None:
            continue
        key = _coalesce_key(show)
        if key not in by_key:
            by_key[key] = show
            order.append(key)
            continue
        existing = by_key[key]
        paths_joined = existing["raw_path"].split("\n")
        if show["raw_path"] not in paths_joined:
            paths_joined.append(show["raw_path"])
            existing["raw_path"] = "\n".join(paths_joined)
            note = existing.get("notes") or ""
            multipart = "multipart raw FLAC"
            existing["notes"] = (
                multipart if not note else f"{note}; {multipart}"
                if multipart not in note
                else note
            )
    return [by_key[k] for k in order]
