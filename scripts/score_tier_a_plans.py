#!/usr/bin/env python3
"""Score Tier A continuous extracts against known_cuts (Jon-aligned)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dat_tracker.boundaries import summarize_comparison  # noqa: E402
from dat_tracker.calibration_split import summarize_split_scores  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tier-a-root",
        type=Path,
        default=ROOT / "data" / "calibration_tier_a",
    )
    parser.add_argument(
        "--work-root",
        type=Path,
        default=ROOT / "data" / "work",
    )
    parser.add_argument("--tolerance", type=float, default=15.0)
    parser.add_argument("--gate-mean", type=float, default=0.80)
    parser.add_argument("--gate-min", type=float, default=0.70)
    args = parser.parse_args()

    scored: list[dict] = []
    missing: list[str] = []
    for known_path in sorted(args.tier_a_root.glob("*/known_cuts.json")):
        show_id = known_path.parent.name
        plan_path = args.work_root / show_id / "tracking_plan_gemini.json"
        if not plan_path.is_file():
            missing.append(show_id)
            continue
        known = json.loads(known_path.read_text())["cuts_sec"]
        hyp = json.loads(plan_path.read_text())["cuts_sec"]
        metrics = summarize_comparison(
            reference_cuts=known,
            hypothesis_cuts=hyp,
            tolerance_sec=args.tolerance,
        )
        scored.append({"id": show_id, **metrics})
        print(
            f"{show_id}\tF1={metrics['f1']:.3f}\t"
            f"tracks={metrics['hypothesis_tracks']}/{metrics['reference_tracks']}\t"
            f"Δ={metrics['track_count_delta']:+d}"
        )

    if missing:
        print("missing plans:", ", ".join(missing), file=sys.stderr)
    if not scored:
        print("No Tier A plans to score", file=sys.stderr)
        return 1

    summary = summarize_split_scores(scored)
    print(
        f"\nsplit=tier_a n={summary['n']} mean_f1={summary['mean_f1']:.3f} "
        f"min_f1={summary['min_f1']:.3f} "
        f"track_|Δ|≤1={summary['track_count_ok_fraction']:.0%}"
    )
    mean_ok = summary["mean_f1"] >= args.gate_mean
    min_ok = summary["min_f1"] >= args.gate_min
    track_ok = summary["track_count_ok_fraction"] >= 0.80
    print(
        f"gate mean≥{args.gate_mean:.2f}: {'PASS' if mean_ok else 'FAIL'}  "
        f"min≥{args.gate_min:.2f}: {'PASS' if min_ok else 'FAIL'}  "
        f"trackΔ: {'PASS' if track_ok else 'FAIL'}"
    )
    return 0 if mean_ok and min_ok and track_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
