#!/usr/bin/env python3
"""Build synthetic continuous FLACs + known-cut JSON for Tier B packages."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dat_tracker.resplit import (  # noqa: E402
    concatenate_tracks_lossless,
    known_cuts_from_track_dir,
    synthetic_raw_path_for,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=ROOT / "catalog" / "calibration_tier_b.json",
    )
    parser.add_argument(
        "--calibration-root",
        type=Path,
        default=ROOT / "data" / "calibration",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Rebuild synthetic FLACs even if they already exist",
    )
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text())
    built = 0
    skipped = 0
    for show in manifest["shows"]:
        show_id = show["id"]
        package_dir = args.calibration_root / show_id
        if not package_dir.is_dir():
            print(f"SKIP missing package dir: {package_dir}", file=sys.stderr)
            skipped += 1
            continue
        out_flac = synthetic_raw_path_for(args.calibration_root, show_id)
        cuts_json = package_dir / "known_cuts.json"
        try:
            cuts, tracks = known_cuts_from_track_dir(package_dir)
        except FileNotFoundError as exc:
            print(f"SKIP {show_id}: {exc}", file=sys.stderr)
            skipped += 1
            continue
        if args.force or not out_flac.is_file():
            print(f"concat {show_id} ({len(tracks)} tracks) -> {out_flac.name}")
            concatenate_tracks_lossless(tracks, out_flac)
        else:
            print(f"exists {out_flac}")
        payload = {
            "id": show_id,
            "split": show.get("split"),
            "tracks": [p.name for p in tracks],
            "cuts_sec": cuts,
            "total_sec": cuts[-1] if cuts else 0.0,
            "synthetic_raw": str(out_flac.relative_to(ROOT))
            if out_flac.is_relative_to(ROOT)
            else str(out_flac),
        }
        cuts_json.write_text(json.dumps(payload, indent=2) + "\n")
        built += 1
    print(f"done: wrote metadata for {built} shows (skipped {skipped})")
    return 0 if built else 1


if __name__ == "__main__":
    raise SystemExit(main())
