#!/usr/bin/env python3
"""Build a heuristic tracking-plan dry-run for a Tier B synthetic show."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dat_tracker.boundaries import probe_duration_seconds  # noqa: E402
from dat_tracker.energy import propose_cuts_from_audio  # noqa: E402
from dat_tracker.speech import (  # noqa: E402
    cuts_from_speech_islands,
    filter_plausible_speech_segments,
    merge_speech_islands,
    parse_whisper_segments,
    propose_speech_prioritized_cuts,
)
from dat_tracker.tracking_plan import build_draft_tracking_plan  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--show-id", default="del2001-04-27.flac16")
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Write plan JSON (default: data/work/<id>/tracking_plan_draft.json)",
    )
    args = parser.parse_args()

    package = ROOT / "data" / "calibration" / args.show_id
    synth = package / "synthetic_continuous.flac"
    cache = package / "whisper_segments.json"
    if not synth.is_file() or not cache.is_file():
        print(f"Need {synth} and cached {cache}", file=sys.stderr)
        return 1

    duration = probe_duration_seconds(synth)
    segs = parse_whisper_segments(json.loads(cache.read_text()))
    energy = propose_cuts_from_audio(synth, min_separation_sec=60.0)
    cuts = propose_speech_prioritized_cuts(
        segs, energy_cuts=energy, duration_sec=duration
    )
    islands = merge_speech_islands(
        filter_plausible_speech_segments(segs, max_seg_sec=20.0)
    )
    speech_starts = set(
        cuts_from_speech_islands(islands, duration_sec=duration)[1:-1]
    )

    rel_source = str(synth.relative_to(ROOT))
    plan = build_draft_tracking_plan(
        show_id=args.show_id,
        source_path=rel_source,
        duration_sec=duration,
        cuts_sec=cuts,
        speech_islands=islands,
        speech_cut_sec=speech_starts,
    )

    out = args.out
    if out is None:
        out = ROOT / "data" / "work" / args.show_id / "tracking_plan_draft.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(plan, indent=2) + "\n")
    print(json.dumps(plan, indent=2))
    print(f"wrote {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
