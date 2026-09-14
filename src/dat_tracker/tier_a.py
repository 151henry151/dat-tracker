"""Tier A: real Live Bluegrass raw ↔ Jon package calibration helpers."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from dat_tracker.align import align_snippet_in_raw
from dat_tracker.boundaries import (
    list_track_flacs,
    probe_duration_seconds,
    reference_cuts_from_ground_truth_dir,
)
from dat_tracker.ffmpeg_tools import ffmpeg_bin


def tier_a_known_cuts_from_reference(reference_cuts: list[float]) -> list[float]:
    """Show-local known cuts for an extract that starts at the aligned show open."""
    return [float(c) for c in reference_cuts]


def resolve_raw_flac_path(
    *,
    project_root: Path,
    raw_path: str,
    extracted_root: Path | None = None,
) -> Path:
    """Map a catalog raw_path to an on-disk FLAC under data/raw/extracted/."""
    root = extracted_root or (project_root / "data" / "raw" / "extracted")
    candidate = root / raw_path
    if candidate.is_file():
        return candidate
    # Multipart catalog rows may list several paths; caller should pick one.
    raise FileNotFoundError(f"Missing extracted raw FLAC: {candidate}")


def prepare_tier_a_continuous(
    *,
    show_id: str,
    raw_flac: Path,
    ground_truth_dir: Path,
    out_dir: Path,
    snippet_duration_sec: float = 45.0,
    pad_end_sec: float = 5.0,
) -> dict[str, Any]:
    """Align Jon t01 into raw, extract that show span, write known_cuts.json.

    Returns paths and alignment metadata. The continuous extract is show-local
    (starts near 0 at the Jon package open) so scoring matches Tier B layout.
    """
    tracks = list_track_flacs(ground_truth_dir)
    if not tracks:
        raise FileNotFoundError(f"No tracks in {ground_truth_dir}")
    ref_cuts = reference_cuts_from_ground_truth_dir(ground_truth_dir)
    show_dur = float(ref_cuts[-1])
    offset, dist = align_snippet_in_raw(
        raw_flac,
        tracks[0],
        snippet_duration_sec=snippet_duration_sec,
    )
    # Clamp extract to raw duration.
    raw_dur = probe_duration_seconds(raw_flac)
    start = max(0.0, float(offset))
    end = min(raw_dur, start + show_dur + pad_end_sec)
    if end - start < show_dur * 0.5:
        raise RuntimeError(
            f"Aligned extract too short for {show_id}: "
            f"offset={offset:.1f} raw_dur={raw_dur:.1f} show_dur={show_dur:.1f}"
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    continuous = out_dir / "continuous.flac"
    # Lossless copy of the span (re-encode flac from decoded PCM slice).
    subprocess.run(
        [
            ffmpeg_bin(),
            "-y",
            "-ss",
            f"{start:.3f}",
            "-to",
            f"{end:.3f}",
            "-i",
            str(raw_flac),
            "-c:a",
            "flac",
            str(continuous),
        ],
        check=True,
        capture_output=True,
    )
    known = tier_a_known_cuts_from_reference(ref_cuts)
    # If extract is slightly longer than Jon duration, keep Jon end cut and add extract end.
    extract_dur = probe_duration_seconds(continuous)
    if abs(known[-1] - extract_dur) > 1.0:
        # Prefer extract endpoint as master duration for track_show.
        known = [*known[:-1], float(extract_dur)]
    known_path = out_dir / "known_cuts.json"
    known_path.write_text(
        json.dumps(
            {
                "show_id": show_id,
                "cuts_sec": known,
                "align_offset_sec": start,
                "align_distance": dist,
                "raw_flac": str(raw_flac),
                "ground_truth_dir": str(ground_truth_dir),
            },
            indent=2,
        )
        + "\n"
    )
    return {
        "show_id": show_id,
        "continuous": continuous,
        "known_cuts": known_path,
        "cuts_sec": known,
        "align_offset_sec": start,
        "align_distance": dist,
        "extract_duration_sec": extract_dur,
        "reference_duration_sec": show_dur,
    }
