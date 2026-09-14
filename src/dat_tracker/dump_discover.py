"""Discover continuous FLACs under an operator-chosen dump directory."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from dat_tracker.catalog_io import load_catalog
from dat_tracker.dump_metadata import parse_artists_from_stem, parse_date_from_stem
from dat_tracker.review_discover import (
    ReviewableShow,
    discover_reviewable_shows,
    prefer_plan_path,
    resolve_show_for_review,
    resolve_source_audio,
)


def _artist_date_from_stem(stem: str) -> tuple[str | None, str | None]:
    artists = parse_artists_from_stem(stem)
    artist = " > ".join(artists) if artists else None
    date = parse_date_from_stem(stem)
    return artist, date


def last_dump_root() -> Path | None:
    """Return the last dump directory chosen in dat-review, if saved."""
    try:
        from dat_tracker.review_defaults import user_defaults_path

        path = user_defaults_path()
        if not path.is_file():
            return None
        raw = json.loads(path.read_text())
        if not isinstance(raw, dict):
            return None
        value = raw.get("last_dump_root")
        if not value:
            return None
        candidate = Path(str(value)).expanduser()
        return candidate if candidate.is_dir() else None
    except (OSError, json.JSONDecodeError, TypeError):
        return None


def default_dump_root(
    project_root: Path,
    *,
    use_last: bool = True,
) -> Path | None:
    """Prefer ``data/raw/extracted`` when it has FLACs, else last chosen dump."""
    root = Path(project_root)
    extracted = root / "data" / "raw" / "extracted"
    if extracted.is_dir() and any(extracted.rglob("*.flac")):
        return extracted
    if extracted.is_dir() and any(extracted.rglob("*.FLAC")):
        return extracted
    if use_last:
        return last_dump_root()
    return None


def _normalize_rel(path: str) -> str:
    return path.replace("\\", "/").lstrip("./")


def _catalog_by_raw_path(catalog_dir: Path | None) -> dict[str, dict[str, Any]]:
    if catalog_dir is None or not (Path(catalog_dir) / "shows.json").is_file():
        return {}
    out: dict[str, dict[str, Any]] = {}
    for row in load_catalog(Path(catalog_dir)):
        raw = row.get("raw_path") or ""
        for part in str(raw).split("\n"):
            key = _normalize_rel(part.strip())
            if key:
                out[key] = row
    return out


def show_id_for_flac(
    flac_path: Path,
    *,
    dump_root: Path,
    catalog_dir: Path | None = None,
) -> str:
    """Map a dump FLAC to a stable show id (catalog id when known)."""
    rel = _normalize_rel(str(flac_path.relative_to(Path(dump_root))))
    by_raw = _catalog_by_raw_path(catalog_dir)
    row = by_raw.get(rel)
    if row and row.get("id"):
        return str(row["id"])
    return flac_path.stem


def _index_work_plans_by_source(
    *,
    project_root: Path,
    work_root: Path,
) -> dict[Path, ReviewableShow]:
    """Map resolved source audio → existing reviewable show."""
    indexed: dict[Path, ReviewableShow] = {}
    for show in discover_reviewable_shows(
        project_root=project_root, work_dir=work_root
    ):
        src = show.source_path
        if src is None:
            continue
        try:
            key = src.resolve()
        except OSError:
            key = src
        indexed[key] = show
        try:
            doc = json.loads(show.plan_path.read_text())
        except (OSError, json.JSONDecodeError, TypeError):
            continue
        resolved = resolve_source_audio(
            doc.get("source_path"),
            project_root=project_root,
            show_id=show.show_id,
        )
        if resolved is not None:
            try:
                indexed[resolved.resolve()] = show
            except OSError:
                indexed[resolved] = show
    return indexed


def discover_dump_shows(
    dump_root: Path,
    *,
    project_root: Path,
    work_dir: Path | None = None,
    catalog_dir: Path | None = None,
) -> list[ReviewableShow]:
    """List continuous FLACs under ``dump_root``, linked to work plans when present."""
    root = Path(project_root)
    dump = Path(dump_root)
    if not dump.is_dir():
        return []
    work_root = Path(work_dir) if work_dir is not None else root / "data" / "work"
    cat_dir = Path(catalog_dir) if catalog_dir is not None else root / "catalog"
    by_raw = _catalog_by_raw_path(cat_dir if cat_dir.is_dir() else None)
    by_source = _index_work_plans_by_source(project_root=root, work_root=work_root)

    flacs = sorted(
        {p.resolve(): p for p in list(dump.rglob("*.flac")) + list(dump.rglob("*.FLAC"))}.values(),
        key=lambda p: str(p.relative_to(dump)).lower(),
    )

    shows: list[ReviewableShow] = []
    seen_ids: set[str] = set()
    for flac in flacs:
        try:
            rel = _normalize_rel(str(flac.relative_to(dump)))
        except ValueError:
            continue
        row = by_raw.get(rel)
        try:
            resolved = flac.resolve()
        except OSError:
            resolved = flac

        linked = by_source.get(resolved)
        dump_artist, dump_date = _artist_date_from_stem(flac.stem)
        if linked is not None:
            shows.append(
                ReviewableShow(
                    show_id=linked.show_id,
                    plan_path=linked.plan_path,
                    source_path=flac,
                    review_status=linked.review_status,
                    track_count=linked.track_count,
                    duration_sec=linked.duration_sec,
                    work_dir=linked.work_dir,
                    needs_tracking=False,
                    relative_path=rel,
                    artist=(row or {}).get("artist") or linked.artist or dump_artist,
                    date=(row or {}).get("date") or linked.date or dump_date,
                )
            )
            seen_ids.add(linked.show_id)
            continue

        show_id = str(row["id"]) if row and row.get("id") else flac.stem
        # Prefer an on-disk work dir named after catalog/stem id.
        work_show_dir = work_root / show_id
        plan_path = prefer_plan_path(work_show_dir)
        if plan_path is not None and show_id not in seen_ids:
            found = resolve_show_for_review(
                show_id, project_root=root, work_dir=work_root
            )
            if found is not None:
                shows.append(
                    ReviewableShow(
                        show_id=found.show_id,
                        plan_path=found.plan_path,
                        source_path=flac,
                        review_status=found.review_status,
                        track_count=found.track_count,
                        duration_sec=found.duration_sec,
                        work_dir=found.work_dir,
                        needs_tracking=False,
                        relative_path=rel,
                        artist=(row or {}).get("artist") or found.artist or dump_artist,
                        date=(row or {}).get("date") or found.date or dump_date,
                    )
                )
                seen_ids.add(found.show_id)
                continue

        if show_id in seen_ids:
            continue
        expected_plan = work_show_dir / "tracking_plan_gemini.json"
        shows.append(
            ReviewableShow(
                show_id=show_id,
                plan_path=expected_plan,
                source_path=flac,
                review_status="untracked",
                track_count=0,
                duration_sec=None,
                work_dir=work_show_dir,
                needs_tracking=True,
                relative_path=rel,
                artist=(row or {}).get("artist") or dump_artist,
                date=(row or {}).get("date") or dump_date,
            )
        )
        seen_ids.add(show_id)
    return shows
