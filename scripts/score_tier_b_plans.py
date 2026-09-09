#!/usr/bin/env python3
"""Score existing tracking_plan_gemini.json files by Tier B train/holdout split.

Use --split train while tuning. Re-check --split holdout only after train gains
so we do not chase holdout noise.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dat_tracker.boundaries import summarize_comparison  # noqa: E402
from dat_tracker.calibration_split import (  # noqa: E402
    load_tier_b_manifest,
    show_ids_for_split,
    summarize_split_scores,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=ROOT / "catalog" / "calibration_tier_b.json",
    )
    parser.add_argument(
        "--split",
        choices=("train", "holdout", "all"),
        default="train",
        help="Which manifest split to score (default: train)",
    )
    parser.add_argument(
        "--work-root",
        type=Path,
        default=ROOT / "data" / "work",
    )
    parser.add_argument(
        "--calibration-root",
        type=Path,
        default=ROOT / "data" / "calibration",
    )
    parser.add_argument("--tolerance", type=float, default=15.0)
    parser.add_argument(
        "--gate-mean",
        type=float,
        default=0.85,
        help="Print PASS/FAIL vs this mean F1 (informational)",
    )
    parser.add_argument(
        "--gate-min",
        type=float,
        default=0.70,
        help="Print PASS/FAIL vs this min F1 (informational)",
    )
    args = parser.parse_args()

    rows = load_tier_b_manifest(args.manifest)
    if args.split == "all":
        ids = [str(r["id"]) for r in rows]
    else:
        ids = show_ids_for_split(rows, args.split)

    scored: list[dict] = []
    missing: list[str] = []
    for show_id in ids:
        known_path = args.calibration_root / show_id / "known_cuts.json"
        plan_path = args.work_root / show_id / "tracking_plan_gemini.json"
        if not known_path.is_file() or not plan_path.is_file():
            missing.append(show_id)
            continue
        known = json.loads(known_path.read_text())["cuts_sec"]
        hyp = json.loads(plan_path.read_text())["cuts_sec"]
        metrics = summarize_comparison(
            reference_cuts=known,
            hypothesis_cuts=hyp,
            tolerance_sec=args.tolerance,
        )
        row = {
            "id": show_id,
            "f1": metrics["f1"],
            "precision": metrics["precision"],
            "recall": metrics["recall"],
            "track_count_delta": metrics["track_count_delta"],
            "hypothesis_tracks": metrics["hypothesis_tracks"],
            "reference_tracks": metrics["reference_tracks"],
        }
        scored.append(row)
        print(
            f"{show_id}\tF1={row['f1']:.3f}\t"
            f"tracks={row['hypothesis_tracks']}/{row['reference_tracks']}\t"
            f"Δ={row['track_count_delta']:+d}"
        )

    summary = summarize_split_scores(scored)
    print(
        f"\nsplit={args.split} n={summary['n']} "
        f"mean_f1={summary['mean_f1']:.3f} min_f1={summary['min_f1']:.3f} "
        f"track_|Δ|≤1={summary['track_count_ok_fraction']:.0%}"
    )
    mean_ok = summary["n"] > 0 and summary["mean_f1"] >= args.gate_mean
    min_ok = summary["n"] > 0 and summary["min_f1"] >= args.gate_min
    track_ok = summary["n"] > 0 and summary["track_count_ok_fraction"] >= 0.8
    print(
        f"gate mean≥{args.gate_mean:.2f}: {'PASS' if mean_ok else 'FAIL'}  "
        f"min≥{args.gate_min:.2f}: {'PASS' if min_ok else 'FAIL'}  "
        f"trackΔ: {'PASS' if track_ok else 'FAIL'}"
    )
    if missing:
        print("missing plans/known:", ", ".join(missing), file=sys.stderr)
    return 0 if scored else 1


if __name__ == "__main__":
    raise SystemExit(main())
