#!/usr/bin/env python3
"""Propose silence cuts on a raw FLAC and score against a ground-truth item."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dat_tracker.boundaries import (  # noqa: E402
    probe_duration_seconds,
    reference_cuts_from_ground_truth_dir,
    summarize_comparison,
)
from dat_tracker.silence import (  # noqa: E402
    propose_cuts_from_silences,
    run_silencedetect,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--raw",
        type=Path,
        default=ROOT / "data" / "work" / "jcb2002-08-02" / "020802_JCB_RR.flac",
    )
    parser.add_argument(
        "--ground-truth-id",
        default="jcb2002-08-02",
        help="Item under data/ground_truth/ to score against",
    )
    parser.add_argument(
        "--offset-sec",
        type=float,
        default=0.0,
        help="Assume the ground-truth show starts at this offset in the raw file",
    )
    parser.add_argument("--noise-db", type=float, default=-40.0)
    parser.add_argument("--min-silence", type=float, default=0.8)
    parser.add_argument("--propose-min-silence", type=float, default=1.2)
    parser.add_argument("--tolerance", type=float, default=1.0)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    gt_dir = ROOT / "data" / "ground_truth" / args.ground_truth_id
    if not args.raw.is_file():
        print(f"Missing raw: {args.raw}", file=sys.stderr)
        return 1
    if not gt_dir.is_dir():
        print(f"Missing ground truth: {gt_dir}", file=sys.stderr)
        return 1

    raw_duration = probe_duration_seconds(args.raw)
    print(f"raw duration: {raw_duration:.3f}s", file=sys.stderr)
    print("running silencedetect (may take a few minutes)...", file=sys.stderr)
    regions = run_silencedetect(
        args.raw, noise_db=args.noise_db, min_silence_sec=args.min_silence
    )
    proposed = propose_cuts_from_silences(
        silence_regions=regions,
        duration_sec=raw_duration,
        min_silence_sec=args.propose_min_silence,
    )

    ref = reference_cuts_from_ground_truth_dir(gt_dir)
    # Score only interior show cuts shifted by offset; compare to proposals in window.
    offset = args.offset_sec
    shifted = [c + offset for c in ref]
    show_end = shifted[-1]
    windowed = [c for c in proposed if offset - 0.5 <= c <= show_end + 0.5]
    # Ensure window endpoints present for fair track-count comparison.
    if not windowed or abs(windowed[0] - offset) > 0.5:
        windowed = [offset] + windowed
    if abs(windowed[-1] - show_end) > 0.5:
        windowed = windowed + [show_end]

    summary = summarize_comparison(
        reference_cuts=shifted,
        hypothesis_cuts=windowed,
        tolerance_sec=args.tolerance,
    )
    payload = {
        "raw": str(args.raw),
        "ground_truth_id": args.ground_truth_id,
        "offset_sec": offset,
        "raw_duration_sec": raw_duration,
        "silence_regions": len(regions),
        "proposed_cuts_sec": proposed,
        "windowed_cuts_sec": windowed,
        "reference_cuts_sec": shifted,
        "metrics": summary,
    }
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        m = summary
        print(
            f"silences={len(regions)} proposed_cuts={len(proposed)} "
            f"windowed={len(windowed)} ref_tracks={m['reference_tracks']}"
        )
        print(
            f"offset={offset:.3f}s tolerance={args.tolerance}s "
            f"F1={m['f1']:.3f} precision={m['precision']:.3f} "
            f"recall={m['recall']:.3f} track_delta={m['track_count_delta']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
