#!/usr/bin/env python3
"""Locate ground-truth show openings inside a longer raw FLAC via energy match."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dat_tracker.align import align_snippet_in_raw  # noqa: E402
from dat_tracker.boundaries import list_track_flacs  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--raw",
        type=Path,
        default=ROOT / "data" / "work" / "jcb2002-08-02" / "020802_JCB_RR.flac",
    )
    parser.add_argument(
        "--ground-truth-id",
        action="append",
        dest="ids",
        default=None,
        help="Ground-truth id (repeatable). Default: jcb + prtr for 2002-08-02",
    )
    parser.add_argument("--snippet-duration", type=float, default=45.0)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    ids = args.ids or ["jcb2002-08-02", "prtr2002-08-02"]

    results = []
    for gt_id in ids:
        gt_dir = ROOT / "data" / "ground_truth" / gt_id
        tracks = list_track_flacs(gt_dir)
        if not tracks:
            print(f"No tracks in {gt_dir}", file=sys.stderr)
            return 1
        print(f"aligning {gt_id} using {tracks[0].name} ...", file=sys.stderr)
        offset, dist = align_snippet_in_raw(
            args.raw,
            tracks[0],
            snippet_duration_sec=args.snippet_duration,
        )
        results.append(
            {
                "id": gt_id,
                "snippet": tracks[0].name,
                "offset_sec": offset,
                "distance": dist,
            }
        )
        print(f"{gt_id}: offset={offset:.3f}s distance={dist:.3f}", file=sys.stderr)

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        for row in results:
            print(f"{row['id']}\t{row['offset_sec']:.3f}\t{row['distance']:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
