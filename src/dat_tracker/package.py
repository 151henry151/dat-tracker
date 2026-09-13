"""Package etree-style show.txt and fingerprint.ffp.txt from a tracking plan."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from dat_tracker.show_txt import format_show_txt


def flac_streaminfo_md5(path: Path) -> str:
    """Return the FLAC STREAMINFO audio MD5 (lowercase hex) without metaflac."""
    data = path.read_bytes()
    if data[:4] != b"fLaC":
        raise ValueError(f"not a FLAC file: {path}")
    i = 4
    while i + 4 <= len(data):
        header = data[i]
        i += 1
        length = int.from_bytes(data[i : i + 3], "big")
        i += 3
        block = data[i : i + length]
        i += length
        is_last = bool(header & 0x80)
        block_type = header & 0x7F
        if block_type == 0:
            if len(block) < 34:
                raise ValueError(f"truncated STREAMINFO in {path}")
            return block[18:34].hex()
        if is_last:
            break
    raise ValueError(f"no STREAMINFO block in {path}")


def format_fingerprint_ffp(entries: list[tuple[str, str]]) -> str:
    """Render a simple `.ffp` / fingerprint.ffp.txt body (name:md5 lines)."""
    lines = [f"{name}:{md5.lower()}" for name, md5 in entries]
    return "\n".join(lines) + ("\n" if lines else "")


def _title_for_setlist(track: dict[str, Any]) -> str:
    title = track.get("title")
    track_type = str(track.get("track_type") or "unknown")
    if title:
        text = str(title).strip()
    elif track_type == "banter":
        text = "Banter"
    elif track_type == "tuning":
        text = "Tuning"
    elif track_type == "intro":
        text = "Intro"
    elif track_type == "encore_break":
        text = "Encore break"
    else:
        text = "Unknown"
    if track.get("segue_into_next"):
        if not text.endswith(">"):
            text = f"{text} >"
    return text


def setlist_entries_from_plan(plan: dict[str, Any]) -> list[dict[str, Any]]:
    """Build `{num, title}` rows for format_show_txt from plan tracks."""
    tracks = sorted(plan.get("tracks") or [], key=lambda t: int(t["index"]))
    return [
        {"num": int(track["index"]), "title": _title_for_setlist(track)}
        for track in tracks
    ]


def package_show_from_plan(
    plan: dict[str, Any],
    *,
    track_paths: list[Path],
    out_dir: Path,
    artist: str,
    date: str,
    tracker: str,
    venue: str | None = None,
    city: str | None = None,
    state: str | None = None,
    source: str | None = None,
    transfer: str | None = None,
    transferer: str = "Cate Crowe",
    set_label: str = "One Set",
    force_unreviewed: bool = False,
) -> dict[str, Path]:
    """Write `{show_id}.txt` and `fingerprint.ffp.txt` next to exported tracks."""
    from dat_tracker.review_plan import assert_review_approved_for_package

    assert_review_approved_for_package(plan, force_unreviewed=force_unreviewed)
    out_dir.mkdir(parents=True, exist_ok=True)
    show_id = str(plan["show_id"])
    txt_path = out_dir / f"{show_id}.txt"
    ffp_path = out_dir / "fingerprint.ffp.txt"

    txt = format_show_txt(
        artist=artist,
        date=date,
        venue=venue,
        city=city,
        state=state,
        source=source,
        transfer=transfer,
        transferer=transferer,
        tracker=tracker,
        set_label=set_label,
        tracks=setlist_entries_from_plan(plan),
    )
    txt_path.write_text(txt)

    entries = [
        (path.name, flac_streaminfo_md5(path))
        for path in track_paths
    ]
    ffp_path.write_text(format_fingerprint_ffp(entries))
    return {"txt": txt_path, "ffp": ffp_path}
