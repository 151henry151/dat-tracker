"""Fill blank plan titles/types from Gemini listen notes; seed package metadata."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from dat_tracker.review_defaults import (
    load_operator_defaults,
    merge_builtin_fallbacks,
)
from dat_tracker.review_plan import migrate_tracking_plan
from dat_tracker.tracking_plan import validate_tracking_plan

_NOTE_TIME = re.compile(
    r"^(?:REJECT|ACCEPT|SNAP|IGNORE)\s+(\d+(?:\.\d+)?)s",
    re.IGNORECASE,
)
_MUSIC_TITLE = re.compile(
    r"continuous music\s*\((.+)\)\s*\.?\s*$",
    re.IGNORECASE,
)
_DATE_IN_ID = re.compile(r"(20\d{2}|19\d{2})-(\d{2})-(\d{2})")
_BANTER_HINT = re.compile(
    r"\b(banter|stage break|spoken intro|stage banter)\b",
    re.IGNORECASE,
)
_DATE_ISO = re.compile(r"^(20\d{2}|19\d{2})-(\d{2})-(\d{2})\s*$")
_DATE_MDY = re.compile(
    r"^(\d{1,2})[-/](\d{1,2})[-/](20\d{2}|19\d{2})\s*$"
)
_CITY_STATE = re.compile(
    r"^(.+?),\s*([A-Za-z.]{2,}(?:\.[A-Za-z.]{1,})?)\s*$"
)
_TRACKLIST_START = re.compile(
    r"^(disc\s+\d+|set\s+\d+|one\s+set|\d{1,2}\.\s*\S)",
    re.IGNORECASE,
)
_STATE_ALIASES = {
    "N.C.": "NC",
    "N.C": "NC",
    "NC.": "NC",
    "NORTH CAROLINA": "NC",
    "CALIFORNIA": "CA",
    "CA.": "CA",
}


def _clean_quoted_title(inner: str) -> str:
    """Turn ``'Sailin' Shoes' / 'Cocaine'`` into ``Sailin' Shoes / Cocaine``."""
    s = inner.strip()
    parts = re.split(r"'\s*/\s*'", s)
    cleaned: list[str] = []
    for part in parts:
        p = part.strip().strip("'").strip()
        if p:
            cleaned.append(p)
    return " / ".join(cleaned) if cleaned else s.strip("'")


def _note_time_sec(note: str) -> float | None:
    match = _NOTE_TIME.match(note.strip())
    if not match:
        return None
    return float(match.group(1))


def _titles_in_span(
    notes: list[str], *, start: float, end: float
) -> list[str]:
    found: list[str] = []
    for note in notes:
        t = _note_time_sec(note)
        if t is None or not (start <= t < end):
            continue
        m = _MUSIC_TITLE.search(note)
        if not m:
            continue
        title = _clean_quoted_title(m.group(1))
        if title and title not in found:
            found.append(title)
    return found


def _banter_hits_in_span(notes: list[str], *, start: float, end: float) -> int:
    hits = 0
    for note in notes:
        t = _note_time_sec(note)
        if t is None or not (start <= t < end):
            continue
        if _BANTER_HINT.search(note):
            hits += 1
    return hits


_TYPE_DEFAULT_TITLE = {
    "banter": "Banter",
    "tuning": "Tuning",
    "intro": "Intro",
    "encore_break": "Encore break",
}


def hydrate_plan_from_notes(plan: dict[str, Any]) -> dict[str, Any]:
    """When Gemini left tracks empty, recover titles/types from listen notes.

    Gemini often returns ``tracks: []`` and only names songs inside REJECT/ACCEPT
    note text (``continuous music ('Title')``). The materializer then creates
    unknown/null tracks — this pass fills blanks without overwriting edits.

    Non-song types without a title get Jon/etree-style defaults (``Banter``,
    ``Intro``, …) matching ``package._title_for_setlist``.
    """
    plan = migrate_tracking_plan(plan)
    notes = [str(n) for n in (plan.get("notes") or [])]
    tracks = list(plan.get("tracks") or [])
    changed = False
    for track in tracks:
        start = float(track["start_sec"])
        end = float(track["end_sec"])
        titles = _titles_in_span(notes, start=start, end=end)
        banter_hits = _banter_hits_in_span(notes, start=start, end=end)
        track_type = str(track.get("track_type") or "unknown")

        # Continuous-music note titles belong on songs (or still-unknown
        # tracks we may promote to song). Never stamp them onto banter/etc.
        if (
            not track.get("title")
            and titles
            and track_type in {"song", "unknown"}
        ):
            track["title"] = titles[0]
            changed = True

        if track_type == "unknown":
            if banter_hits > 0 and not titles:
                track["track_type"] = "banter"
                changed = True
            elif titles or (end - start) >= 60.0:
                track["track_type"] = "song"
                changed = True
            track_type = str(track.get("track_type") or "unknown")

        if not track.get("title"):
            default = _TYPE_DEFAULT_TITLE.get(track_type)
            if default:
                track["title"] = default
                changed = True

        if changed and "hydrated_from_notes" not in (track.get("evidence") or []):
            track["evidence"] = list(track.get("evidence") or []) + [
                "hydrated_from_notes"
            ]

    plan["tracks"] = tracks
    if changed:
        notes_out = list(plan.get("notes") or [])
        marker = "Hydrated blank track titles/types from listen notes."
        if marker not in notes_out:
            notes_out.append(marker)
        plan["notes"] = notes_out
    validate_tracking_plan(plan)
    return plan


def lookup_catalog_show(
    show_id: str,
    *,
    project_root: Path | None = None,
) -> dict[str, Any] | None:
    root = project_root or Path.cwd()
    path = root / "catalog" / "calibration_tier_b.json"
    if not path.is_file():
        return None
    import json

    doc = json.loads(path.read_text())
    for row in doc.get("shows") or []:
        if str(row.get("id")) == show_id:
            return dict(row)
    return None


def _normalize_state(raw: str) -> str:
    s = raw.strip()
    key = s.upper()
    if key in _STATE_ALIASES:
        return _STATE_ALIASES[key]
    letters = re.sub(r"[^A-Za-z]", "", s)
    if len(letters) == 2:
        return letters.upper()
    return s


def _parse_date_line(line: str) -> str | None:
    m = _DATE_ISO.match(line.strip())
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    m = _DATE_MDY.match(line.strip())
    if m:
        month = int(m.group(1))
        day = int(m.group(2))
        year = m.group(3)
        return f"{year}-{month:02d}-{day:02d}"
    return None


def parse_published_show_txt(path: Path) -> dict[str, Any]:
    """Best-effort parse of a published etree/info ``.txt`` header.

    Expects a Jon/etree-ish header: artist, venue lines, city/state, date,
    then a source/transfer lineage line. Missing pieces are omitted.
    """
    text = Path(path).read_text(errors="replace")
    lines = [ln.strip() for ln in text.splitlines()]
    while lines and not lines[-1]:
        lines.pop()

    fields: dict[str, Any] = {}
    header: list[str] = []
    body_start = 0
    for i, ln in enumerate(lines):
        if not ln:
            if header:
                body_start = i + 1
                break
            continue
        if _TRACKLIST_START.match(ln) and header:
            body_start = i
            break
        if _parse_date_line(ln):
            header.append(ln)
            body_start = i + 1
            while body_start < len(lines) and not lines[body_start]:
                body_start += 1
            break
        header.append(ln)
    else:
        body_start = len(lines)

    if not header:
        return fields

    fields["artist"] = header[0]
    rest = header[1:]
    date = None
    if rest and _parse_date_line(rest[-1]):
        date = _parse_date_line(rest[-1])
        rest = rest[:-1]
    if date:
        fields["date"] = date

    city = None
    state = None
    venue_parts: list[str] = []
    for ln in rest:
        m = _CITY_STATE.match(ln)
        if m and city is None:
            city = m.group(1).strip()
            state = _normalize_state(m.group(2))
            continue
        venue_parts.append(ln)
    if venue_parts:
        fields["venue"] = venue_parts[0]
        if len(venue_parts) > 1:
            fields["notes"] = "; ".join(venue_parts[1:])
    if city:
        fields["city"] = city
    if state:
        fields["state"] = state

    for ln in lines[body_start:]:
        if not ln:
            continue
        if _TRACKLIST_START.match(ln):
            break
        if len(ln) < 8:
            continue
        lower = ln.lower()
        if any(
            tok in lower
            for tok in (">", "dat", "sbd", "aud", "matrix", "flac", "transfer")
        ):
            fields["source"] = ln
            break

    return {k: v for k, v in fields.items() if v not in (None, "")}


def find_published_show_txt(calibration_dir: Path) -> Path | None:
    """Pick the best published info ``.txt`` under a calibration show dir."""
    if not calibration_dir.is_dir():
        return None
    skip_substr = (
        "ffp",
        "fingerprint",
        "concat",
        "known_cuts",
        "whisper",
        "tracking_plan",
        "waveform",
    )
    candidates: list[Path] = []
    for path in sorted(calibration_dir.glob("*.txt")):
        name = path.name.lower()
        if any(s in name for s in skip_substr):
            continue
        candidates.append(path)
    if not candidates:
        return None

    def score(p: Path) -> tuple[int, int]:
        try:
            text = p.read_text(errors="replace")
        except OSError:
            return (0, 0)
        pts = 0
        for ln in text.splitlines():
            if _parse_date_line(ln.strip()):
                pts += 2
                break
        if ">" in text or "DAT" in text.upper():
            pts += 1
        return (pts, len(text))

    candidates.sort(key=score, reverse=True)
    return candidates[0]


def seed_package_metadata(
    plan: dict[str, Any],
    *,
    artist: str | None = None,
    date: str | None = None,
    tracker: str | None = None,
    venue: str | None = None,
    city: str | None = None,
    state: str | None = None,
    source: str | None = None,
    transfer: str | None = None,
    project_root: Path | None = None,
    calibration_dir: Path | None = None,
) -> dict[str, Any]:
    """Fill empty package fields from CLI, published txt, catalog, and show_id."""
    plan = migrate_tracking_plan(plan)
    pkg = dict(plan.get("package") or {})
    root = project_root or Path.cwd()
    catalog = lookup_catalog_show(str(plan.get("show_id") or ""), project_root=root)

    published: dict[str, Any] = {}
    cal = calibration_dir
    if cal is None and plan.get("show_id"):
        cal = root / "data" / "calibration" / str(plan["show_id"])
    if cal is not None:
        txt = find_published_show_txt(Path(cal))
        if txt is not None:
            published = parse_published_show_txt(txt)

    defaults = merge_builtin_fallbacks(load_operator_defaults(project_root=root))

    def _unset(key: str, cur: Any) -> bool:
        if cur in (None, ""):
            return True
        # Earlier seeds wrote the soft builtin; allow a real operator default to win.
        if key == "tracker" and str(cur).strip().lower() in {
            "dat-tracker",
            "your name",
        }:
            return True
        return False

    def _set(key: str, *candidates: Any) -> None:
        cur = pkg.get(key)
        if not _unset(key, cur):
            return
        for cand in candidates:
            if cand not in (None, ""):
                pkg[key] = cand
                return

    _set("artist", artist, published.get("artist"), (catalog or {}).get("artist"))
    date_from_id = None
    m = _DATE_IN_ID.search(str(plan.get("show_id") or ""))
    if m:
        date_from_id = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    _set(
        "date",
        date,
        published.get("date"),
        (catalog or {}).get("date"),
        date_from_id,
    )
    _set("tracker", tracker, defaults.get("tracker"))
    _set("venue", venue, published.get("venue"))
    _set("city", city, published.get("city"))
    _set("state", state, published.get("state"))
    _set("source", source, published.get("source"))
    _set("transfer", transfer, published.get("transfer"))
    _set("transferer", published.get("transferer"))
    _set("set_label", published.get("set_label"), defaults.get("set_label"))
    _set("notes", published.get("notes"))
    plan["package"] = pkg
    validate_tracking_plan(plan)
    return plan
