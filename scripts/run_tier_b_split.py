#!/usr/bin/env python3
"""Run track_show for every Tier B show in a split (default: train)."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dat_tracker.calibration_split import load_tier_b_manifest, show_ids_for_split  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=ROOT / "catalog" / "calibration_tier_b.json",
    )
    parser.add_argument("--split", choices=("train", "holdout"), default="train")
    parser.add_argument(
        "--refine",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Gemini refine pass (default: on; use --no-refine to skip)",
    )
    parser.add_argument(
        "--skip-package",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Skip FLAC package export (default: skip)",
    )
    parser.add_argument("--tolerance", type=float, default=15.0)
    args = parser.parse_args()

    rows = {str(r["id"]): r for r in load_tier_b_manifest(args.manifest)}
    ids = show_ids_for_split(list(rows.values()), args.split)
    failures: list[str] = []
    for show_id in ids:
        meta = rows[show_id]
        artist = str(meta.get("artist") or show_id)
        date = str(meta.get("date") or "1970-01-01")
        cmd = [
            str(ROOT / ".venv" / "bin" / "python"),
            str(ROOT / "scripts" / "track_show.py"),
            "--show-id",
            show_id,
            "--artist",
            artist,
            "--date",
            date,
            "--reuse-calibration-whisper",
            "--tolerance",
            str(args.tolerance),
        ]
        if args.skip_package:
            cmd.append("--skip-package")
        if args.refine:
            cmd.append("--refine")
        print("RUN", " ".join(cmd), flush=True)
        proc = subprocess.run(cmd, cwd=str(ROOT))
        if proc.returncode != 0:
            failures.append(show_id)
            print(f"FAIL {show_id} exit={proc.returncode}", flush=True)
        else:
            print(f"OK {show_id}", flush=True)

    score = [
        str(ROOT / ".venv" / "bin" / "python"),
        str(ROOT / "scripts" / "score_tier_b_plans.py"),
        "--split",
        args.split,
    ]
    subprocess.run(score, cwd=str(ROOT))
    if failures:
        print("failures:", ", ".join(failures), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
