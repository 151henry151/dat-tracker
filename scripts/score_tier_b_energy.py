#!/usr/bin/env python3
"""Score energy-novelty cut proposals against Tier B known_cuts.json."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dat_tracker.boundaries import summarize_comparison  # noqa: E402
from dat_tracker.energy import propose_cuts_from_audio  # noqa: E402


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
    parser.add_argument("--split", choices=["train", "holdout", "all"], default="all")
    parser.add_argument("--tolerance", type=float, default=2.0)
    parser.add_argument("--min-separation", type=float, default=8.0)
    parser.add_argument("--limit", type=int, default=0, help="Score only first N shows")
    args = parser.parse_args()

    shows = json.loads(args.manifest.read_text())["shows"]
    if args.split != "all":
        shows = [s for s in shows if s.get("split") == args.split]
    if args.limit:
        shows = shows[: args.limit]

    rows = []
    for show in shows:
        show_id = show["id"]
        package = args.calibration_root / show_id
        known_path = package / "known_cuts.json"
        synth = package / "synthetic_continuous.flac"
        if not known_path.is_file() or not synth.is_file():
            print(f"SKIP {show_id}: missing synthetic/known cuts", file=sys.stderr)
            continue
        known = json.loads(known_path.read_text())["cuts_sec"]
        print(f"proposing {show_id} ...", file=sys.stderr)
        hyp = propose_cuts_from_audio(
            synth, min_separation_sec=args.min_separation
        )
        metrics = summarize_comparison(
            reference_cuts=known,
            hypothesis_cuts=hyp,
            tolerance_sec=args.tolerance,
        )
        row = {
            "id": show_id,
            "split": show.get("split"),
            "ref_tracks": metrics["reference_tracks"],
            "hyp_tracks": metrics["hypothesis_tracks"],
            "f1": metrics["f1"],
            "precision": metrics["precision"],
            "recall": metrics["recall"],
        }
        rows.append(row)
        print(
            f"{show_id}\tsplit={row['split']}\t"
            f"F1={row['f1']:.3f}\tP={row['precision']:.3f}\t"
            f"R={row['recall']:.3f}\t"
            f"tracks={row['hyp_tracks']}/{row['ref_tracks']}"
        )

    if not rows:
        return 1
    mean_f1 = sum(r["f1"] for r in rows) / len(rows)
    print(f"mean_f1={mean_f1:.3f} over {len(rows)} shows (tol={args.tolerance}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
