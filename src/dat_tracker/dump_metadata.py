"""Infer package metadata from Live Bluegrass-style dump paths and filenames.

Dump FLACs often have no published show.txt. Useful signals live in:
- Filename date prefixes (``MMDDYYYY``, ``YYMMDD``, ``YYYYMMDD``, ``YYYY-MM-DD``)
- Artist chains after ``-`` separated by unicode arrows / ``>``
- Parent festival folder names
- ``Dave W Flacs`` / ``Brian H Flacs`` path segments
- Sibling J-card ``.jpg`` / ``.jpeg`` / ``.png`` photos
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

# Common dump abbreviations → display names (filename tokens).
_ARTIST_EXPAND: dict[str, str] = {
    "bgbrethren": "Bluegrass Brethren",
    "bgplayoff": "Bluegrass Playoff",
    "jcb": "John Cowan Band",
    "los": "Leftover Salmon",
    "sci": "String Cheese Incident",
    "ymsb": "Yonder Mountain String Band",
    "jmp": "Jazz Mandolin Project",
    "rre": "Railroad Earth",
    "ocms": "Old Crow Medicine Show",
    "prtr": "Peter Rowan / Tony Rice",
    "hotrize": "Hot Rize",
    "silvcity": "Silver City",
    "despmeas": "Desperate Measures",
    "bluehwy": "Blue Highway",
    "wearyhearts": "Weary Hearts",
    "mccroury": "Del McCoury Band",
    "cjones": "Chris Jones",
    "jwingfield": "Julie Wingfield",
    "wingfield": "Julie Wingfield",
    "lampkin": "Lampkin",
    "sturgis": "Sturgis",
    "vincent": "Rhonda Vincent",
    "lawson": "Doyle Lawson",
    "doyle": "Doyle Lawson",
    "shiflett": "Shiflett",
    "mcnasty": "McNasty",
}

_DATE_ISO = re.compile(r"(19\d{2}|20\d{2})-(\d{2})-(\d{2})")
_DATE_YYYYMMDD = re.compile(r"^(19\d{2}|20\d{2})(\d{2})(\d{2})(?:[_-]|\b)")
_DATE_MMDDYYYY = re.compile(r"^(\d{2})(\d{2})(19\d{2}|20\d{2})(?:[_-]|\b)")
_DATE_YYMMDD = re.compile(r"^(\d{2})(\d{2})(\d{2})(?:[_-]|\b)")

_ARROW_SPLIT = re.compile(r"\s*(?:→|->|>|–|—)\s*")
_FESTIVAL_SUFFIX = re.compile(
    r"\s*[-–—]\s*(?:January|February|March|April|May|June|July|August|"
    r"September|October|November|December)\s+\d{4}\s*$",
    re.IGNORECASE,
)

_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}

_DAVE_TRANSFER = "DAT > Sony PCM-2600 > ESI U24XL > Audacity > FLAC"
_BRIAN_SOURCE = (
    "Unknown (Brian H collection — often AUD mic or festival FM; "
    "see J-card photo when present)"
)
_DAVE_SOURCE = "SBD > DAT (Dave Ward Collection — see J-card / catalog when present)"


def expand_artist_token(token: str) -> str:
    """Expand a known dump abbreviation; otherwise tidy the raw token."""
    raw = (token or "").strip()
    if not raw:
        return raw
    # Strip trailing -E / -L / -AUD / early/late markers common in dump names.
    cleaned = re.sub(
        r"[-_](?:E|L|AUD|SBD|early|late|FM)\d*$",
        "",
        raw,
        flags=re.IGNORECASE,
    ).strip("-_ ")
    key = re.sub(r"[^A-Za-z0-9]", "", cleaned).lower()
    if key in _ARTIST_EXPAND:
        return _ARTIST_EXPAND[key]
    # Title-case dotted / underscored tokens lightly.
    if "_" in cleaned or "." in cleaned:
        return cleaned.replace("_", " ").replace(".", " ").strip()
    return cleaned


def parse_date_from_stem(stem: str) -> str | None:
    """Return ``YYYY-MM-DD`` parsed from a dump or etree-style stem, if any."""
    text = str(stem or "").strip()
    if not text:
        return None

    m = _DATE_ISO.search(text)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"

    m = _DATE_YYYYMMDD.match(text)
    if m:
        return _validated_ymd(m.group(1), m.group(2), m.group(3))

    m = _DATE_MMDDYYYY.match(text)
    if m:
        return _validated_ymd(m.group(3), m.group(1), m.group(2))

    m = _DATE_YYMMDD.match(text)
    if m:
        yy, mo, dd = int(m.group(1)), m.group(2), m.group(3)
        # Dave W dump convention: YYMMDD with 00–79 → 2000–2079, 80–99 → 1980–1999.
        year = 2000 + yy if yy < 80 else 1900 + yy
        return _validated_ymd(str(year), mo, dd)

    return None


def _validated_ymd(year: str, month: str, day: str) -> str | None:
    try:
        y, m, d = int(year), int(month), int(day)
        if not (1 <= m <= 12 and 1 <= d <= 31 and 1900 <= y <= 2100):
            return None
        return f"{y:04d}-{m:02d}-{d:02d}"
    except ValueError:
        return None


def parse_artists_from_stem(stem: str) -> list[str]:
    """Artist tokens from the dump stem after the date / tape-index prefix."""
    text = str(stem or "").strip()
    if not text:
        return []

    # Drop leading date chunk.
    rest = text
    for pat in (_DATE_YYYYMMDD, _DATE_MMDDYYYY, _DATE_YYMMDD):
        m = pat.match(rest)
        if m:
            rest = rest[m.end() :].lstrip("_-")
            break
    else:
        m = _DATE_ISO.search(rest)
        if m and m.start() == 0:
            rest = rest[m.end() :].lstrip("_-.")

    # Drop tape index like HF_01 / HF_02 / t01 before the artist list.
    rest = re.sub(r"^(?:[A-Za-z]{1,8}_?\d{1,2}|t\d{1,2})[-_]", "", rest, count=1)

    if not rest:
        return []

    # Prefer the segment after the first hyphen when it looks like artist list.
    if "-" in rest and _ARROW_SPLIT.search(rest):
        # e.g. HF_01-McNasty→Shiflett — already stripped HF_01 above, or still has it
        parts = rest.split("-", 1)
        if len(parts) == 2 and _ARROW_SPLIT.search(parts[1]):
            rest = parts[1]
        elif _ARROW_SPLIT.search(parts[0]):
            rest = parts[0]

    if _ARROW_SPLIT.search(rest):
        tokens = [t for t in _ARROW_SPLIT.split(rest) if t.strip()]
    elif "_" in rest and not rest.lower().startswith("jcb"):
        # Single artist with underscores — one token
        tokens = [rest]
    else:
        tokens = [rest]

    artists: list[str] = []
    for tok in tokens:
        expanded = expand_artist_token(tok)
        if expanded and expanded not in artists:
            artists.append(expanded)
    return artists


def parse_venue_from_folder(folder_name: str) -> str | None:
    """Festival / venue from a dump parent folder name."""
    name = str(folder_name or "").strip()
    if not name:
        return None
    lower = name.lower()
    if lower in {"dave w flacs", "brian h flacs", "misc", "sci"}:
        return None
    if lower.startswith("brian h flacs") or lower.startswith("dave w flacs"):
        return None
    cleaned = _FESTIVAL_SUFFIX.sub("", name).strip(" -–—")
    # Folders like "2003 Huck Finn Country & Bluegrass Jam"
    cleaned = re.sub(r"^\d{4}\s+", "", cleaned).strip()
    if len(cleaned) < 3:
        return None
    return cleaned


def collection_from_path(path: Path, *, dump_root: Path | None = None) -> str | None:
    """Return ``Dave Ward Collection`` / ``Brian H Collection`` from path parts."""
    try:
        parts = [p.lower() for p in Path(path).parts]
    except Exception:
        return None
    joined = "/".join(parts)
    if "brian h" in joined:
        return "Brian H Collection"
    if "dave w" in joined:
        return "Dave Ward Collection"
    if dump_root is not None:
        try:
            rel = Path(path).resolve().relative_to(Path(dump_root).resolve())
            return collection_from_path(rel)
        except Exception:
            pass
    return None


def find_sibling_jcard_images(source_audio: Path) -> list[Path]:
    """Images that share the FLAC stem (J-card photos next to the dump file)."""
    source = Path(source_audio)
    if not source.is_file():
        return []
    stem = source.stem
    parent = source.parent
    out: list[Path] = []
    for path in sorted(parent.iterdir()):
        if not path.is_file():
            continue
        if path.stem != stem:
            continue
        if path.suffix.lower() in _IMAGE_SUFFIXES:
            out.append(path)
    return out


def infer_dump_package_fields(
    source_audio: Path,
    *,
    dump_root: Path | None = None,
    show_id: str | None = None,
) -> dict[str, Any]:
    """Best-effort package fields from dump path + filename (no network)."""
    source = Path(source_audio)
    stem = show_id or source.stem
    fields: dict[str, Any] = {}

    date = parse_date_from_stem(stem)
    if date:
        fields["date"] = date

    artists = parse_artists_from_stem(stem)
    if artists:
        fields["artist"] = " > ".join(artists)
        if len(artists) > 1:
            fields["set_label"] = "Multi-artist continuous"
            fields["notes"] = "Artists on tape (from filename): " + "; ".join(artists)

    # Walk parents for festival folder + collection.
    venue = None
    for parent in source.parents:
        name = parent.name
        if dump_root is not None:
            try:
                parent.resolve().relative_to(Path(dump_root).resolve())
            except ValueError:
                break
        candidate = parse_venue_from_folder(name)
        if candidate and venue is None:
            venue = candidate
        if dump_root is not None and parent.resolve() == Path(dump_root).resolve():
            break
        # Don't walk above dump root forever — stop after a few levels if no dump_root
        if dump_root is None and parent == source.anchor:
            break

    if venue:
        fields["venue"] = venue

    collection = collection_from_path(source, dump_root=dump_root)
    if collection:
        fields["collection_subjects"] = [collection]

    fields["transferer"] = "Cate Crowe"
    fields["transfer"] = _DAVE_TRANSFER
    if collection == "Brian H Collection":
        fields["source"] = _BRIAN_SOURCE
    elif collection == "Dave Ward Collection":
        fields["source"] = _DAVE_SOURCE
    else:
        fields["source"] = "Unknown (see dump Read Me / J-card)"

    return {k: v for k, v in fields.items() if v not in (None, "", [])}
