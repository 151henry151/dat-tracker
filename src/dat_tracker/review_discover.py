"""Discover shows that have tracking plans ready for dat-review."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PLAN_NAME_PREFERENCE = (
    "tracking_plan_gemini.json",
    "tracking_plan.json",
)

# Never treat the LLM baseline snapshot as the working review plan.
_PLAN_GLOB_SKIP = frozenset(
    {
        "tracking_plan_as_delivered.json",
    }
)


@dataclass(frozen=True)
class ReviewableShow:
    show_id: str
    plan_path: Path
    source_path: Path | None
    review_status: str
    track_count: int
    duration_sec: float | None
    work_dir: Path
    needs_tracking: bool = False
    relative_path: str = ""
    artist: str | None = None
    date: str | None = None

    @property
    def has_audio(self) -> bool:
        return self.source_path is not None and self.source_path.is_file()


def prefer_plan_path(work_dir: Path) -> Path | None:
    """Return the preferred tracking-plan path under a show work dir."""
    work_dir = Path(work_dir)
    for name in PLAN_NAME_PREFERENCE:
        candidate = work_dir / name
        if candidate.is_file():
            return candidate
    matches = sorted(
        p
        for p in work_dir.glob("tracking_plan*.json")
        if p.name not in _PLAN_GLOB_SKIP
    )
    return matches[0] if matches else None


def resolve_source_audio(
    source_path: str | Path | None,
    *,
    project_root: Path,
    show_id: str,
) -> Path | None:
    """Resolve continuous FLAC for waveform/playback."""
    root = Path(project_root)
    candidates: list[Path] = []
    if source_path:
        raw = Path(source_path)
        candidates.append(raw if raw.is_absolute() else root / raw)
    candidates.append(
        root / "data" / "calibration" / show_id / "synthetic_continuous.flac"
    )
    # Common alternate names under calibration / work.
    for base in (
        root / "data" / "calibration" / show_id,
        root / "data" / "work" / show_id,
    ):
        if base.is_dir():
            for name in (
                "synthetic_continuous.flac",
                "continuous.flac",
                f"{show_id}.flac",
            ):
                candidates.append(base / name)
    seen: set[Path] = set()
    for path in candidates:
        try:
            resolved = path.resolve()
        except OSError:
            resolved = path
        if resolved in seen:
            continue
        seen.add(resolved)
        if path.is_file():
            return path
    return None


def _load_plan_summary(plan_path: Path) -> dict[str, Any]:
    try:
        return json.loads(plan_path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def discover_reviewable_shows(
    *,
    project_root: Path,
    work_dir: Path | None = None,
) -> list[ReviewableShow]:
    """List shows under ``data/work`` that have a tracking plan JSON."""
    root = Path(project_root)
    work_root = Path(work_dir) if work_dir is not None else root / "data" / "work"
    if not work_root.is_dir():
        return []

    shows: list[ReviewableShow] = []
    for child in sorted(work_root.iterdir(), key=lambda p: p.name.lower()):
        if not child.is_dir():
            continue
        plan_path = prefer_plan_path(child)
        if plan_path is None:
            continue
        doc = _load_plan_summary(plan_path)
        show_id = str(doc.get("show_id") or child.name)
        review = doc.get("review") if isinstance(doc.get("review"), dict) else {}
        status = str(review.get("status") or "pending")
        tracks = doc.get("tracks") if isinstance(doc.get("tracks"), list) else []
        duration = doc.get("duration_sec")
        source = resolve_source_audio(
            doc.get("source_path"),
            project_root=root,
            show_id=show_id,
        )
        shows.append(
            ReviewableShow(
                show_id=show_id,
                plan_path=plan_path,
                source_path=source,
                review_status=status,
                track_count=len(tracks),
                duration_sec=float(duration) if duration is not None else None,
                work_dir=child,
            )
        )
    return shows


def resolve_show_for_review(
    show_id: str,
    *,
    project_root: Path,
    work_dir: Path | None = None,
) -> ReviewableShow | None:
    """Find one show by id (exact match on directory name or plan show_id)."""
    needle = show_id.strip()
    for show in discover_reviewable_shows(
        project_root=project_root, work_dir=work_dir
    ):
        if show.show_id == needle or show.work_dir.name == needle:
            return show
    # Direct path: work/<id> even if discovery missed casing.
    root = Path(project_root)
    work_root = Path(work_dir) if work_dir is not None else root / "data" / "work"
    direct = work_root / needle
    plan_path = prefer_plan_path(direct) if direct.is_dir() else None
    if plan_path is None:
        return None
    doc = _load_plan_summary(plan_path)
    sid = str(doc.get("show_id") or needle)
    review = doc.get("review") if isinstance(doc.get("review"), dict) else {}
    tracks = doc.get("tracks") if isinstance(doc.get("tracks"), list) else []
    duration = doc.get("duration_sec")
    return ReviewableShow(
        show_id=sid,
        plan_path=plan_path,
        source_path=resolve_source_audio(
            doc.get("source_path"), project_root=root, show_id=sid
        ),
        review_status=str(review.get("status") or "pending"),
        track_count=len(tracks),
        duration_sec=float(duration) if duration is not None else None,
        work_dir=direct,
    )
