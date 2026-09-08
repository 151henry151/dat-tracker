#!/usr/bin/env python3
"""Sparse Gemini listen dry-run on a Tier B synthetic show (Del by default)."""

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
from dat_tracker.gemini_tracker import (  # noqa: E402
    request_tracking_plan_from_clips,
    speech_anchor_cuts_with_probes,
)
from dat_tracker.speech import parse_whisper_segments  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--show-id", default="del2001-04-27.flac16")
    parser.add_argument("--half-window", type=float, default=8.0)
    parser.add_argument("--tolerance", type=float, default=15.0)
    parser.add_argument("--max-gap", type=float, default=240.0)
    parser.add_argument("--probe-step", type=float, default=90.0)
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Write plan JSON (default under data/work/<id>/)",
    )
    args = parser.parse_args()

    package = ROOT / "data" / "calibration" / args.show_id
    synth = package / "synthetic_continuous.flac"
    known_path = package / "known_cuts.json"
    whisper_cache = package / "whisper_segments.json"
    if not synth.is_file() or not known_path.is_file():
        print(f"Missing {synth} or {known_path}", file=sys.stderr)
        return 1
    if not whisper_cache.is_file():
        print(f"Missing cached ASR {whisper_cache}", file=sys.stderr)
        return 1

    known = json.loads(known_path.read_text())["cuts_sec"]
    duration = probe_duration_seconds(synth)
    segs = parse_whisper_segments(json.loads(whisper_cache.read_text()))
    anchors, probes = speech_anchor_cuts_with_probes(
        segs,
        duration_sec=duration,
        max_gap_sec=args.max_gap,
        probe_step_sec=args.probe_step,
    )

    work = ROOT / "data" / "work" / args.show_id / "gemini_listen"
    print(
        f"anchors={[round(c, 1) for c in anchors]} "
        f"probes={[round(c, 1) for c in probes]} "
        f"half_window={args.half_window}s",
        file=sys.stderr,
    )
    plan = request_tracking_plan_from_clips(
        source_audio=synth,
        show_id=args.show_id,
        source_path=str(synth.relative_to(ROOT)),
        duration_sec=duration,
        candidate_cuts_sec=anchors,
        probe_centers_sec=probes,
        work_dir=work,
        half_window_sec=args.half_window,
        project_root=ROOT,
    )

    out = args.out or (
        ROOT / "data" / "work" / args.show_id / "tracking_plan_gemini.json"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(plan, indent=2) + "\n")

    m = summarize_comparison(
        reference_cuts=known,
        hypothesis_cuts=plan["cuts_sec"],
        tolerance_sec=args.tolerance,
    )
    print(json.dumps(plan, indent=2))
    print(
        f"{args.show_id}\tgemini_sparse\tF1={m['f1']:.3f}\t"
        f"P={m['precision']:.3f}\tR={m['recall']:.3f}\t"
        f"tracks={m['hypothesis_tracks']}/{m['reference_tracks']}\t"
        f"cuts={[round(c, 1) for c in plan['cuts_sec']]}",
        file=sys.stderr,
    )
    print(f"wrote {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
