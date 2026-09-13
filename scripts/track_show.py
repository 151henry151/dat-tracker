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
    parser.add_argument("--artist", default=None)
    parser.add_argument("--date", default=None, help="YYYY-MM-DD")
    parser.add_argument("--tracker", default="dat-tracker")
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
        "--accept-all",
        action="store_true",
        help="Headless review Approve-all before packaging (skip TUI)",
    )
    parser.add_argument(
        "--force-unreviewed",
        action="store_true",
        help="Package without review approval (escape hatch)",
    )
    parser.add_argument(
        "--no-interactive-review",
        action="store_true",
        help="Do not spawn the TUI; require prior approval or --accept-all/--force-unreviewed",
    )
    parser.add_argument(
        "--refine",
        action="store_true",
        help="Extra Gemini listen pass to snap cuts (off by default; costly)",
    )
    parser.add_argument(
        "--no-speech-snap",
        action="store_true",
        help="Disable forward snap of cuts onto nearby speech onsets",
    )
    parser.add_argument(
        "--force-speech-snap",
        action="store_true",
        help="Force speech snap even when --refine is set (refine defaults snap off)",
    )
    parser.add_argument(
        "--refine-only",
        action="store_true",
        help="Refine an existing tracking_plan_gemini.json without re-proposing",
    )
    parser.add_argument(
        "--speech-snap-only",
        action="store_true",
        help="Apply speech forward-snap to an existing plan (no Gemini call)",
    )
    parser.add_argument(
        "--gap-fill",
        action="store_true",
        help="Run overlong-gap INSERT listen when the plan looks under-segmented",
    )
    parser.add_argument(
        "--gap-fill-max-seg-sec",
        type=float,
        default=480.0,
        help="Segment length that triggers --gap-fill (default: 480.0)",
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

    if args.speech_snap_only:
        from dat_tracker.refine_cuts import (
            rebuild_tracks_from_cuts,
            snap_cuts_forward_to_speech,
        )
        from dat_tracker.speech import (
            filter_plausible_speech_segments,
            merge_speech_islands,
            parse_whisper_segments,
        )

        plan_path = ROOT / "data" / "work" / args.show_id / "tracking_plan_gemini.json"
        cache = cal / "whisper_segments.json"
        if not plan_path.is_file() or not cache.is_file():
            print(f"Need {plan_path} and {cache}", file=sys.stderr)
            return 1
        plan = json.loads(plan_path.read_text())
        segs = parse_whisper_segments(json.loads(cache.read_text()))
        islands = merge_speech_islands(
            filter_plausible_speech_segments(segs, max_seg_sec=20.0)
        )
        snapped = snap_cuts_forward_to_speech(
            list(plan["cuts_sec"]),
            speech_islands=islands,
            duration_sec=float(plan["duration_sec"]),
        )
        plan = rebuild_tracks_from_cuts(plan, snapped)
        plan_path.write_text(json.dumps(plan, indent=2) + "\n")
        result = {"plan": plan, "paths": {"plan": str(plan_path)}}
    elif args.refine_only:
        from dat_tracker.gemini_tracker import refine_tracking_plan_cuts

        plan_path = ROOT / "data" / "work" / args.show_id / "tracking_plan_gemini.json"
        if not plan_path.is_file():
            print(f"Missing {plan_path}", file=sys.stderr)
            return 1
        plan = json.loads(plan_path.read_text())
        plan = refine_tracking_plan_cuts(
            plan,
            source_audio=source,
            work_dir=ROOT / "data" / "work" / args.show_id / "gemini_refine",
            project_root=ROOT,
        )
        plan_path.write_text(json.dumps(plan, indent=2) + "\n")
        result = {"plan": plan, "paths": {"plan": str(plan_path)}}
    else:
        whisper_cache = None
        if args.reuse_calibration_whisper:
            cand = cal / "whisper_segments.json"
            if cand.is_file():
                whisper_cache = cand

        result = run_track_show(
            source_audio=source,
            show_id=args.show_id,
            work_root=ROOT / "data" / "work",
            artist=args.artist or "Unknown Artist",
            date=args.date or "1970-01-01",
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
            refine=args.refine,
            speech_snap=(
                False
                if args.no_speech_snap
                else True
                if args.force_speech_snap
                else None
            ),
            gap_fill=args.gap_fill,
            gap_fill_max_seg_sec=args.gap_fill_max_seg_sec,
            accept_all_review=args.accept_all,
            force_unreviewed=args.force_unreviewed,
            interactive_review=not args.no_interactive_review,
        )
        if not args.skip_package and (not args.artist or not args.date):
            print(
                "warning: package used placeholder artist/date; pass --artist and --date",
                file=sys.stderr,
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
