#!/usr/bin/env python3
"""Score fused silence+energy proposals against Tier B known cuts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dat_tracker.boundaries import (  # noqa: E402
    probe_duration_seconds,
    summarize_comparison,
)
from dat_tracker.candidates import fuse_candidate_cuts  # noqa: E402
from dat_tracker.energy import propose_cuts_from_audio  # noqa: E402
from dat_tracker.silence import (  # noqa: E402
    propose_cuts_from_silences,
    run_silencedetect,
)


def propose_fused(path: Path, *, require_both: bool) -> list[float]:
    duration = probe_duration_seconds(path)
    regions = run_silencedetect(path, noise_db=-40.0, min_silence_sec=0.5)
    silence_cuts = propose_cuts_from_silences(
        silence_regions=regions,
        duration_sec=duration,
        min_silence_sec=0.8,
        pad_sec=1.0,
    )
    energy_cuts = propose_cuts_from_audio(path, min_separation_sec=8.0)
    return fuse_candidate_cuts(
        {"silence": silence_cuts, "energy": energy_cuts},
        merge_tolerance_sec=1.0,
        require_sources=("silence", "energy") if require_both else None,
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
    parser.add_argument("--split", choices=["train", "holdout", "all"], default="holdout")
    parser.add_argument("--tolerance", type=float, default=3.0)
    parser.add_argument("--require-both", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
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
            print(f"SKIP {show_id}", file=sys.stderr)
            continue
        known = json.loads(known_path.read_text())["cuts_sec"]
        print(f"proposing {show_id} ...", file=sys.stderr)
        hyp = propose_fused(synth, require_both=args.require_both)
        metrics = summarize_comparison(
            reference_cuts=known,
            hypothesis_cuts=hyp,
            tolerance_sec=args.tolerance,
        )
        print(
            f"{show_id}\tF1={metrics['f1']:.3f}\t"
            f"P={metrics['precision']:.3f}\tR={metrics['recall']:.3f}\t"
            f"tracks={metrics['hypothesis_tracks']}/{metrics['reference_tracks']}"
        )
        rows.append(metrics["f1"])
    if not rows:
        return 1
    print(f"mean_f1={sum(rows)/len(rows):.3f} over {len(rows)} shows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
