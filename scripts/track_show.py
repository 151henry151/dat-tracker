#!/usr/bin/env python3
"""Track one continuous FLAC: Whisper → sparse Gemini listen → package."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dat_tracker.track_show import (  # noqa: E402
    run_track_show,
    score_plan_against_known,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--show-id", required=True)
    parser.add_argument(
        "--source",
        type=Path,
        default=None,
        help="Continuous FLAC (default: data/calibration/<id>/synthetic_continuous.flac)",
    )
    parser.add_argument("--artist", required=True)
    parser.add_argument("--date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--tracker", default="Henry")
    parser.add_argument("--venue", default=None)
    parser.add_argument("--city", default=None)
    parser.add_argument("--state", default=None)
    parser.add_argument("--source-line", default=None)
    parser.add_argument("--transfer", default=None)
    parser.add_argument("--whisper-model", default="base")
    parser.add_argument("--tolerance", type=float, default=15.0)
    parser.add_argument(
        "--skip-package",
        action="store_true",
        help="Only write the Gemini tracking plan (no FLAC/txt/ffp export)",
    )
    parser.add_argument(
        "--reuse-calibration-whisper",
        action="store_true",
        help="Prefer data/calibration/<id>/whisper_segments.json when present",
    )
    args = parser.parse_args()

    cal = ROOT / "data" / "calibration" / args.show_id
    source = args.source or (cal / "synthetic_continuous.flac")
    if not source.is_file():
        print(f"Missing source {source}", file=sys.stderr)
        return 1

    whisper_cache = None
    if args.reuse_calibration_whisper:
        cand = cal / "whisper_segments.json"
        if cand.is_file():
            whisper_cache = cand

    result = run_track_show(
        source_audio=source,
        show_id=args.show_id,
        work_root=ROOT / "data" / "work",
        artist=args.artist,
        date=args.date,
        tracker=args.tracker,
        venue=args.venue,
        city=args.city,
        state=args.state,
        source_line=args.source_line,
        transfer=args.transfer,
        project_root=ROOT,
        whisper_model=args.whisper_model,
        whisper_cache_path=whisper_cache,
        skip_package=args.skip_package,
    )

    known_path = cal / "known_cuts.json"
    if known_path.is_file():
        known = json.loads(known_path.read_text())["cuts_sec"]
        metrics = score_plan_against_known(
            known_cuts=known,
            plan=result["plan"],
            tolerance_sec=args.tolerance,
        )
        result["metrics"] = metrics
        print(
            f"{args.show_id}\tF1={metrics['f1']:.3f}\t"
            f"P={metrics['precision']:.3f}\tR={metrics['recall']:.3f}\t"
            f"tracks={metrics['hypothesis_tracks']}/{metrics['reference_tracks']}\t"
            f"cuts={[round(c, 1) for c in result['plan']['cuts_sec']]}",
            file=sys.stderr,
        )

    print(json.dumps({"paths": result["paths"], "metrics": result.get("metrics")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
