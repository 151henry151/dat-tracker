"""Build a complete etree-style package under data/out (and work mirror)."""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from dat_tracker.export_tracks import export_tracks_from_plan
from dat_tracker.package import package_show_from_plan
from dat_tracker.review_plan import (
    assert_review_approved_for_package,
    package_fields_from_plan,
)


@dataclass
class PackageResult:
    """Paths and counts from a successful ``build_package`` run."""

    show_id: str
    out_dir: Path
    work_dir: Path
    track_paths: list[Path] = field(default_factory=list)
    track_count: int = 0
    txt_path: Path | None = None
    ffp_path: Path | None = None


def _album_tag(pkg: dict[str, Any]) -> str:
    artist = str(pkg.get("artist") or "Unknown Artist").strip()
    date = str(pkg.get("date") or "").strip()
    venue = str(pkg.get("venue") or "").strip()
    parts = [p for p in (artist, date, venue) if p]
    return " - ".join(parts) if parts else artist


def apply_vorbis_tags(
    track_path: Path,
    *,
    plan: dict[str, Any],
    track: dict[str, Any],
) -> None:
    """Write etree-ish Vorbis comments onto one exported FLAC."""
    from mutagen.flac import FLAC

    pkg = package_fields_from_plan(plan)
    audio = FLAC(str(track_path))
    audio.delete()
    artist = str(pkg.get("artist") or "Unknown Artist")
    title = str(track.get("title") or f"Track {track.get('index')}")
    if track.get("segue_into_next") and not title.rstrip().endswith(">"):
        title = f"{title.rstrip()} >"
    audio["artist"] = artist
    audio["title"] = title
    audio["tracknumber"] = str(int(track["index"]))
    if pkg.get("date"):
        audio["date"] = str(pkg["date"])
    album = _album_tag(pkg)
    if album:
        audio["album"] = album
    if pkg.get("venue"):
        audio["venue"] = str(pkg["venue"])
    if pkg.get("city") or pkg.get("state"):
        loc = ", ".join(
            p for p in (pkg.get("city"), pkg.get("state")) if p not in (None, "")
        )
        if loc:
            audio["location"] = loc
    audio.save()


def build_package(
    plan: dict[str, Any],
    *,
    source_audio: Path,
    project_root: Path | None = None,
    force_unreviewed: bool = False,
    progress: Callable[[str], None] | None = None,
) -> PackageResult:
    """Export tagged tracks + show.txt + ffp into data/out and work mirror."""
    assert_review_approved_for_package(plan, force_unreviewed=force_unreviewed)
    root = Path(project_root) if project_root is not None else Path.cwd()
    show_id = str(plan["show_id"])
    source = Path(source_audio)
    if not source.is_file():
        raise FileNotFoundError(source)

    out_dir = root / "data" / "out" / show_id
    work_dir = root / "data" / "work" / show_id / "package"
    out_dir.mkdir(parents=True, exist_ok=True)
    work_dir.mkdir(parents=True, exist_ok=True)

    def _log(msg: str) -> None:
        if progress:
            progress(msg)

    _log(f"Exporting tracks to {out_dir}…")
    track_paths = export_tracks_from_plan(source, plan, out_dir)

    tracks_by_index = {
        int(t["index"]): t for t in (plan.get("tracks") or [])
    }
    for path in track_paths:
        # Filename …_tNN.flac
        stem = path.stem
        try:
            idx = int(stem.rsplit("_t", 1)[-1])
        except ValueError:
            continue
        track = tracks_by_index.get(idx) or {
            "index": idx,
            "title": None,
            "segue_into_next": False,
        }
        _log(f"Tagging {path.name}…")
        apply_vorbis_tags(path, plan=plan, track=track)

    pkg = package_fields_from_plan(plan)
    _log("Writing show.txt and fingerprint.ffp.txt…")
    written = package_show_from_plan(
        plan,
        track_paths=track_paths,
        out_dir=out_dir,
        artist=str(pkg.get("artist") or "Unknown Artist"),
        date=str(pkg.get("date") or "1970-01-01"),
        tracker=str(pkg.get("tracker") or "dat-tracker"),
        venue=pkg.get("venue"),
        city=pkg.get("city"),
        state=pkg.get("state"),
        source=pkg.get("source"),
        transfer=pkg.get("transfer"),
        transferer=str(pkg.get("transferer") or "Cate Crowe"),
        set_label=str(pkg.get("set_label") or "One Set"),
        force_unreviewed=force_unreviewed,
    )

    _log(f"Mirroring package to {work_dir}…")
    for path in list(track_paths) + [written["txt"], written["ffp"]]:
        dest = work_dir / path.name
        shutil.copy2(path, dest)

    return PackageResult(
        show_id=show_id,
        out_dir=out_dir,
        work_dir=work_dir,
        track_paths=track_paths,
        track_count=len(track_paths),
        txt_path=written["txt"],
        ffp_path=written["ffp"],
    )
