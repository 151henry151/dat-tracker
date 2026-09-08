"""Synthetic continuous FLAC re-split helpers for Tier B/C calibration."""

from __future__ import annotations

import subprocess
from pathlib import Path

from dat_tracker.boundaries import (
    cuts_from_durations,
    list_track_flacs,
    probe_duration_seconds,
)


def known_cuts_from_track_dir(directory: Path) -> tuple[list[float], list[Path]]:
    """Return (cut times, ordered track paths) from a published package dir."""
    tracks = [
        path
        for path in list_track_flacs(directory)
        if path.name != "synthetic_continuous.flac"
    ]
    if not tracks:
        raise FileNotFoundError(f"No track FLACs in {directory}")
    durations = [probe_duration_seconds(path) for path in tracks]
    return cuts_from_durations(durations), tracks


def _ffmpeg_concat_path(path: Path) -> str:
    """Quote a path for ffmpeg concat demuxer (escape embedded single quotes)."""
    resolved = str(path.resolve()).replace("'", r"'\''")
    return f"file '{resolved}'"


def build_concat_list_file(tracks: list[Path], out_path: Path) -> Path:
    """Write an ffmpeg concat demuxer list for lossless stream copy."""
    lines = [f"{_ffmpeg_concat_path(path)}\n" for path in tracks]
    out_path.write_text("".join(lines))
    return out_path


def synthetic_raw_path_for(calibration_root: Path, show_id: str) -> Path:
    return calibration_root / show_id / "synthetic_continuous.flac"


def concatenate_tracks_lossless(
    tracks: list[Path],
    out_flac: Path,
    *,
    concat_list: Path | None = None,
) -> Path:
    """Concatenate track FLACs into one continuous FLAC via ffmpeg.

    Re-encodes to FLAC (still lossless). Stream-copy concat often stops after the
    first file when packages have mismatched FLAC stream metadata.
    """
    if not tracks:
        raise ValueError("No tracks to concatenate")
    out_flac.parent.mkdir(parents=True, exist_ok=True)
    list_path = concat_list or (out_flac.parent / "concat_list.txt")
    build_concat_list_file(tracks, list_path)
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_path),
            "-c:a",
            "flac",
            str(out_flac),
        ],
        check=True,
    )
    return out_flac
