#!/usr/bin/env python3
"""Print Jon ground-truth track boundary times for a calibration item."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dat_tracker.boundaries import (  # noqa: E402
    list_track_flacs,
    probe_duration_seconds,
    reference_cuts_from_ground_truth_dir,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "identifier",
        nargs="?",
        default="jcb2002-08-02",
        help="Ground-truth item id under data/ground_truth/",
    )
    parser.add_argument(
        "--ground-truth-root",
        type=Path,
        default=ROOT / "data" / "ground_truth",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON",
    )
    args = parser.parse_args()

    directory = args.ground_truth_root / args.identifier
    if not directory.is_dir():
        print(f"Missing ground-truth dir: {directory}", file=sys.stderr)
        return 1

    tracks = list_track_flacs(directory)
    durations = [probe_duration_seconds(p) for p in tracks]
    cuts = reference_cuts_from_ground_truth_dir(directory)
    payload = {
        "id": args.identifier,
        "tracks": [
            {"file": p.name, "duration_sec": d, "start_sec": cuts[i]}
            for i, (p, d) in enumerate(zip(tracks, durations, strict=True))
        ],
        "cuts_sec": cuts,
        "total_sec": cuts[-1] if cuts else 0.0,
    }
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"{args.identifier}: {len(tracks)} tracks, {payload['total_sec']:.3f}s")
        for row in payload["tracks"]:
            print(
                f"  {row['start_sec']:10.3f}s  {row['duration_sec']:8.3f}s  {row['file']}"
            )
        print("cuts_sec:", ", ".join(f"{c:.3f}" for c in cuts))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
