#!/usr/bin/env python3
"""Run faster-whisper on a calibration synthetic FLAC and score speech-edge cuts."""

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
from dat_tracker.speech import (  # noqa: E402
    cuts_from_speech_segments,
    parse_whisper_segments,
    transcribe_faster_whisper,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--show-id",
        default="del2001-04-27.flac16",
        help="Calibration package id under data/calibration/",
    )
    parser.add_argument("--model", default="base")
    parser.add_argument("--tolerance", type=float, default=3.0)
    args = parser.parse_args()

    package = ROOT / "data" / "calibration" / args.show_id
    synth = package / "synthetic_continuous.flac"
    known_path = package / "known_cuts.json"
    if not synth.is_file() or not known_path.is_file():
        print(f"Missing {synth} or {known_path}", file=sys.stderr)
        return 1

    known = json.loads(known_path.read_text())["cuts_sec"]
    duration = probe_duration_seconds(synth)
    cache = package / "whisper_segments.json"
    if cache.is_file():
        print(f"loading cached {cache}", file=sys.stderr)
        payload = json.loads(cache.read_text())
    else:
        print(f"transcribing {synth} with faster-whisper ({args.model})...", file=sys.stderr)
        payload = transcribe_faster_whisper(synth, model_size=args.model)
        cache.write_text(json.dumps(payload, indent=2) + "\n")

    segs = parse_whisper_segments(payload)
    speech_cuts = cuts_from_speech_segments(segs, duration_sec=duration)

    regions = run_silencedetect(synth, noise_db=-40.0, min_silence_sec=0.5)
    silence_cuts = propose_cuts_from_silences(
        silence_regions=regions, duration_sec=duration, min_silence_sec=0.8
    )
    energy_cuts = propose_cuts_from_audio(synth, min_separation_sec=8.0)
    fused = fuse_candidate_cuts(
        {"silence": silence_cuts, "energy": energy_cuts, "speech": speech_cuts},
        merge_tolerance_sec=1.5,
    )

    for label, cuts in (
        ("speech", speech_cuts),
        ("silence+energy+speech", fused),
    ):
        m = summarize_comparison(
            reference_cuts=known, hypothesis_cuts=cuts, tolerance_sec=args.tolerance
        )
        print(
            f"{args.show_id}\t{label}\tF1={m['f1']:.3f}\t"
            f"P={m['precision']:.3f}\tR={m['recall']:.3f}\t"
            f"tracks={m['hypothesis_tracks']}/{m['reference_tracks']}\t"
            f"speech_segs={len(segs)}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
