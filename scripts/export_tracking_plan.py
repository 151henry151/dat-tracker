#!/usr/bin/env python3
"""Export FLAC tracks from a tracking-plan JSON (Gemini or heuristic draft)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dat_tracker.boundaries import probe_duration_seconds  # noqa: E402
from dat_tracker.export_tracks import export_tracks_from_plan  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--plan",
        type=Path,
        required=True,
        help="Path to tracking_plan JSON",
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=None,
        help="Continuous source FLAC (default: plan source_path under repo root)",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Output directory (default: data/work/<show_id>/tracks)",
    )
    args = parser.parse_args()

    plan = json.loads(args.plan.read_text())
    source = args.source
    if source is None:
        rel = plan.get("source_path")
        if not rel:
            print("plan missing source_path; pass --source", file=sys.stderr)
            return 1
        source = ROOT / rel
    out_dir = args.out_dir or (ROOT / "data" / "work" / plan["show_id"] / "tracks")

    paths = export_tracks_from_plan(source, plan, out_dir)
    for path in paths:
        dur = probe_duration_seconds(path)
        print(f"{path.name}\t{dur:.3f}s\t{path}")
    print(f"exported {len(paths)} tracks → {out_dir}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
