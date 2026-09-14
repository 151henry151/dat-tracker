"""Export lossless FLAC track files from a structured tracking plan."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Callable


def etree_track_filename(show_id: str, index: int, title: str | None = None) -> str:
    """Build `{show_id}_tNN.flac` (title is reserved for tags, not the path)."""
    del title  # titles go in Vorbis tags later; keep filenames machine-stable
    return f"{show_id}_t{index:02d}.flac"


def segment_specs_from_plan(plan: dict[str, Any]) -> list[dict[str, Any]]:
    """Derive ordered export segments from plan tracks (preferred) or cuts_sec."""
    show_id = str(plan["show_id"])
    tracks = plan.get("tracks") or []
    if tracks:
        specs: list[dict[str, Any]] = []
        for track in sorted(tracks, key=lambda t: int(t["index"])):
            index = int(track["index"])
            title = track.get("title")
            specs.append(
                {
                    "index": index,
                    "start_sec": float(track["start_sec"]),
                    "end_sec": float(track["end_sec"]),
                    "filename": etree_track_filename(show_id, index, title=title),
                    "title": title,
                    "track_type": track.get("track_type"),
                }
            )
        return specs

    cuts = [float(c) for c in plan.get("cuts_sec") or []]
    if len(cuts) < 2:
        raise ValueError("tracking plan needs tracks or at least two cuts_sec")
    specs = []
    for i, (start, end) in enumerate(zip(cuts, cuts[1:], strict=False), start=1):
        specs.append(
            {
                "index": i,
                "start_sec": start,
                "end_sec": end,
                "filename": etree_track_filename(show_id, i),
                "title": None,
                "track_type": None,
            }
        )
    return specs


from dat_tracker.ffmpeg_tools import ffmpeg_bin


def export_audio_segment(
    source: Path,
    dest: Path,
    *,
    start_sec: float,
    end_sec: float,
) -> Path:
    """Cut [start_sec, end_sec) from source into a FLAC (re-encode, lossless)."""
    if end_sec <= start_sec:
        raise ValueError(f"invalid segment {start_sec}–{end_sec}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    duration = end_sec - start_sec
    subprocess.run(
        [
            ffmpeg_bin(),
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-ss",
            f"{start_sec:.6f}",
            "-t",
            f"{duration:.6f}",
            "-i",
            str(source),
            "-c:a",
            "flac",
            str(dest),
        ],
        check=True,
    )
    return dest


def export_tracks_from_plan(
    source: Path,
    plan: dict[str, Any],
    out_dir: Path,
    *,
    on_progress: Callable[[str, float], None] | None = None,
) -> list[Path]:
    """Write one FLAC per plan track under out_dir; return paths in order."""
    if not source.is_file():
        raise FileNotFoundError(source)
    specs = segment_specs_from_plan(plan)
    n = max(len(specs), 1)
    paths: list[Path] = []
    for i, spec in enumerate(specs):
        dest = out_dir / str(spec["filename"])
        if on_progress is not None:
            on_progress(
                f"Exporting track {i + 1}/{len(specs)}: {dest.name}…",
                i / n,
            )
        export_audio_segment(
            source,
            dest,
            start_sec=float(spec["start_sec"]),
            end_sec=float(spec["end_sec"]),
        )
        paths.append(dest)
    if on_progress is not None and specs:
        on_progress(f"Exported {len(paths)} tracks", 1.0)
    return paths
