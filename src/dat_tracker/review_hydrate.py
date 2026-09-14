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
# Older Gemini dumps: ``112.94s: REJECT - continuous music/singing (Title).``
_NOTE_TIME_LEGACY = re.compile(
    r"^(\d+(?:\.\d+)?)s\s*:",
    re.IGNORECASE,
)
_MUSIC_TITLE = re.compile(
    r"continuous music(?:/singing)?\s*\((.+)\)\s*\.?\s*$",
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
    r"^(disc\s+\d+|set\s+\d+|set\s+[ivxlcdm]+|one\s+set|\d{1,2}\.\s*\S)",
    re.IGNORECASE,
)
_SETLIST_SECTION = re.compile(
    r"^(disc\s+\d+|set\s+[ivxlcdm\d]+|one\s+set)\b",
    re.IGNORECASE,
)
_SETLIST_TRACK = re.compile(
    r"^(\d{1,2})\s*[.\-\)]\s*(.+)$|^(\d{1,2})\s+(.+)$"
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
    text = note.strip()
    match = _NOTE_TIME.match(text)
    if match:
        return float(match.group(1))
    match = _NOTE_TIME_LEGACY.match(text)
    if match:
        return float(match.group(1))
    return None


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
    """Count interior banter evidence; ignore SNAP boundary notes at ``start``."""
    hits = 0
    for note in notes:
        t = _note_time_sec(note)
        # Boundary SNAPs often say "banter onset" while belonging to the cut,
        # not the body of the following track.
        if t is None or not (start < t < end):
            continue
        text = note.strip()
        if re.match(r"^(?:\d+(?:\.\d+)?s\s*:\s*)?SNAP\b", text, re.IGNORECASE):
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

        # Infer type for unknown tracks. Also allow correcting a prior weak
        # hydrate that stamped a blank long span as song when notes later
        # (or with a better parser) show banter — but do not fight a titled song.
        evidence = list(track.get("evidence") or [])
        weak_blank_song = (
            track_type == "song"
            and not track.get("title")
            and not titles
            and "hydrated_from_notes" in evidence
        )
        if track_type == "unknown" or weak_blank_song:
            if banter_hits > 0 and not titles:
                track["track_type"] = "banter"
                changed = True
            elif track_type == "unknown" and (
                titles or (end - start) >= 60.0
            ):
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
        lower = ln.lower()
        if lower.startswith("transferred by:"):
            fields["transferer"] = ln.split(":", 1)[1].strip()
            continue
        if lower.startswith("transfer:") and not lower.startswith("transferred"):
            fields["transfer"] = ln.split(":", 1)[1].strip()
            continue
        if lower.startswith("source:"):
            fields["source"] = ln.split(":", 1)[1].strip()
            continue
        if lower.startswith("taped by:") or lower.startswith("recorded by:"):
            # Optional credit; keep in notes if empty.
            credit = ln.split(":", 1)[1].strip()
            if credit and not fields.get("notes"):
                fields["notes"] = ln.strip()
            continue
        if len(ln) < 8:
            continue
        if any(
            tok in lower
            for tok in (">", "dat", "sbd", "aud", "matrix", "flac")
        ):
            # Unlabeled lineage — prefer as source only when still empty.
            if not fields.get("source"):
                fields["source"] = ln
            elif not fields.get("transfer") and "flac" in lower:
                fields["transfer"] = ln

    return {k: v for k, v in fields.items() if v not in (None, "")}


def _normalize_setlist_title(raw: str) -> str | None:
    title = raw.strip().rstrip(".").strip()
    if not title or title in {"?", "-"}:
        return None
    # "A>B>C" → "A > B > C"
    title = re.sub(r"\s*>\s*", " > ", title)
    title = re.sub(r"\s+", " ", title).strip()
    return title or None


def parse_published_setlist(path: Path) -> list[str]:
    """Extract numbered setlist titles from a published show ``.txt``."""
    text = Path(path).read_text(errors="replace")
    titles: list[str] = []
    in_list = False
    for raw in text.splitlines():
        ln = raw.strip()
        if not ln:
            continue
        if _SETLIST_SECTION.match(ln):
            in_list = True
            continue
        m = _SETLIST_TRACK.match(ln)
        if not m:
            if in_list and titles and not ln[0].isdigit():
                # Notes / footer after the list.
                if ln.lower().startswith("note"):
                    break
            continue
        # Dates like ``08-30-2002`` can look like ``08`` + title.
        if _parse_date_line(ln):
            continue
        in_list = True
        body = m.group(2) if m.group(2) is not None else m.group(4)
        title = _normalize_setlist_title(body or "")
        if title:
            titles.append(title)
    return titles


def hydrate_titles_from_published_setlist(
    plan: dict[str, Any],
    *,
    project_root: Path | None = None,
    calibration_dir: Path | None = None,
) -> dict[str, Any]:
    """Fill blank *song* titles from the published calibration setlist.

    Assigns titles in order to blank ``song`` (and long ``unknown``) tracks,
    skipping banter/tuning/intro/encore. Does not overwrite existing titles.
    """
    plan = migrate_tracking_plan(plan)
    root = project_root or Path.cwd()
    cal = calibration_dir
    if cal is None and plan.get("show_id"):
        cal = root / "data" / "calibration" / str(plan["show_id"])
    if cal is None:
        return plan
    txt = find_published_show_txt(Path(cal))
    if txt is None:
        return plan
    titles = parse_published_setlist(txt)
    if not titles:
        return plan

    tracks = list(plan.get("tracks") or [])
    title_i = 0
    changed = False
    for track in tracks:
        if title_i >= len(titles):
            break
        if track.get("title"):
            continue
        track_type = str(track.get("track_type") or "unknown")
        if track_type in {"banter", "tuning", "intro", "encore_break"}:
            continue
        if track_type == "unknown":
            # Only claim long unknowns as songs for setlist mapping.
            span = float(track["end_sec"]) - float(track["start_sec"])
            if span < 60.0:
                continue
            track["track_type"] = "song"
        track["title"] = titles[title_i]
        title_i += 1
        changed = True
        evidence = list(track.get("evidence") or [])
        if "hydrated_from_published_setlist" not in evidence:
            evidence.append("hydrated_from_published_setlist")
            track["evidence"] = evidence

    plan["tracks"] = tracks
    if changed:
        notes = list(plan.get("notes") or [])
        marker = "Hydrated blank song titles from published show.txt setlist."
        if marker not in notes:
            notes.append(marker)
        plan["notes"] = notes
    validate_tracking_plan(plan)
    return plan


def _merge_surplus_score(track: dict[str, Any]) -> float:
    """Lower score = more willing to absorb this track into its neighbor."""
    dur = max(0.01, float(track["end_sec"]) - float(track["start_sec"]))
    typ = str(track.get("track_type") or "unknown")
    score = dur
    if typ in {"banter", "tuning", "intro", "encore_break", "unknown"}:
        score *= 0.35
    if dur < 90.0:
        score *= 0.45
    if not track.get("title"):
        score *= 0.85
    return score


def reconcile_track_count_to_published_setlist(
    plan: dict[str, Any],
    *,
    project_root: Path | None = None,
    calibration_dir: Path | None = None,
) -> dict[str, Any]:
    """When the plan has more tracks than the published setlist, merge extras.

    Prefers absorbing short / banter / unknown islands into the *following*
    song (delete the cut at the island's end). Under-segmentation is only
    noted — we do not invent cuts from the setlist alone.
    """
    from dat_tracker.review_edits import delete_mid_cut

    plan = migrate_tracking_plan(plan)
    root = project_root or Path.cwd()
    cal = calibration_dir
    if cal is None and plan.get("show_id"):
        cal = root / "data" / "calibration" / str(plan["show_id"])
    if cal is None:
        return plan
    txt = find_published_show_txt(Path(cal))
    if txt is None:
        return plan
    titles = parse_published_setlist(txt)
    if not titles:
        return plan

    target = len(titles)
    tracks = list(plan.get("tracks") or [])
    if len(tracks) == target:
        return plan

    notes = list(plan.get("notes") or [])
    if len(tracks) < target:
        marker = (
            f"Published setlist has {target} songs but plan has {len(tracks)} "
            "tracks (under-segmented); left cuts unchanged for review."
        )
        if marker not in notes:
            notes.append(marker)
            plan["notes"] = notes
            plan["needs_review"] = True
        validate_tracking_plan(plan)
        return plan

    merged = 0
    while len(plan.get("tracks") or []) > target:
        tracks = list(plan.get("tracks") or [])
        # Merge the weakest non-final track into the following track.
        best_i = None
        best_score = None
        for i in range(len(tracks) - 1):
            score = _merge_surplus_score(tracks[i])
            if best_score is None or score < best_score:
                best_score = score
                best_i = i
        if best_i is None:
            break
        # Cut index at the end of track best_i (1-based cuts: track i ends at cuts[i+1]).
        cut_index = best_i + 1
        before = len(plan["tracks"])
        plan = delete_mid_cut(plan, cut_index=cut_index)
        if len(plan.get("tracks") or []) >= before:
            break
        merged += 1

    if merged:
        marker = (
            f"Reconciled track count to published setlist ({target} songs) "
            f"by merging {merged} surplus cut(s)."
        )
        notes = list(plan.get("notes") or [])
        if marker not in notes:
            notes.append(marker)
        plan["notes"] = notes
    validate_tracking_plan(plan)
    return plan


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
    use_llm_extract: bool = True,
    llm_extract_fn: Any | None = None,
) -> dict[str, Any]:
    """Fill empty package fields from CLI, companions (LLM), catalog, and show_id."""
    from dat_tracker.review_package_extract import (
        _EXTRACT_NOTE,
        extract_package_fields_from_companions,
        gather_companion_sources,
    )

    plan = migrate_tracking_plan(plan)
    pkg = dict(plan.get("package") or {})
    root = project_root or Path.cwd()
    catalog = lookup_catalog_show(str(plan.get("show_id") or ""), project_root=root)

    published: dict[str, Any] = {}
    cal = calibration_dir
    if cal is None and plan.get("show_id"):
        cal = root / "data" / "calibration" / str(plan["show_id"])
    ran_llm_extract = False
    if cal is not None and Path(cal).is_dir():
        notes_list = [str(n) for n in (plan.get("notes") or [])]
        already_extracted = _EXTRACT_NOTE in notes_list
        want_llm = bool(use_llm_extract) and not already_extracted
        published = extract_package_fields_from_companions(
            Path(cal),
            use_llm=want_llm,
            project_root=root,
            llm_extract_fn=llm_extract_fn,
        )
        if want_llm:
            ctx = gather_companion_sources(Path(cal))
            ran_llm_extract = bool(ctx["text_files"] or ctx["filenames"])

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

    if ran_llm_extract:
        notes = [str(n) for n in (plan.get("notes") or [])]
        if _EXTRACT_NOTE not in notes:
            notes.append(_EXTRACT_NOTE)
            plan["notes"] = notes

    plan["package"] = pkg
    validate_tracking_plan(plan)
    return plan
