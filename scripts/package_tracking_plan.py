#!/usr/bin/env python3
"""Export tracks from a plan and write show.txt + fingerprint.ffp.txt."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dat_tracker.export_tracks import export_tracks_from_plan  # noqa: E402
from dat_tracker.package import package_show_from_plan  # noqa: E402


def _date_from_show_id(show_id: str) -> str | None:
    match = re.search(r"(20\d{2}|19\d{2})-(\d{2})-(\d{2})", show_id)
    if not match:
        return None
    return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--source", type=Path, default=None)
    parser.add_argument("--out-dir", type=Path, default=None)
    parser.add_argument("--artist", default="Unknown Artist")
    parser.add_argument("--date", default=None)
    parser.add_argument("--tracker", default="dat-tracker")
    parser.add_argument("--venue", default=None)
    parser.add_argument("--city", default=None)
    parser.add_argument("--state", default=None)
    parser.add_argument("--source-line", default=None, dest="source_line")
    parser.add_argument("--transfer", default=None)
    parser.add_argument("--skip-export", action="store_true")
    args = parser.parse_args()

    plan = json.loads(args.plan.read_text())
    show_id = plan["show_id"]
    source = args.source
    if source is None and plan.get("source_path"):
        source = ROOT / plan["source_path"]
    out_dir = args.out_dir or (ROOT / "data" / "work" / show_id / "package")
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.skip_export:
        track_paths = sorted(out_dir.glob(f"{show_id}_t*.flac"))
        if not track_paths:
            print(f"No tracks in {out_dir}; omit --skip-export", file=sys.stderr)
            return 1
    else:
        if source is None or not source.is_file():
            print("Need --source or plan source_path for export", file=sys.stderr)
            return 1
        track_paths = export_tracks_from_plan(source, plan, out_dir)

    date = args.date or _date_from_show_id(show_id) or "1970-01-01"
    paths = package_show_from_plan(
        plan,
        track_paths=track_paths,
        out_dir=out_dir,
        artist=args.artist,
        date=date,
        tracker=args.tracker,
        venue=args.venue,
        city=args.city,
        state=args.state,
        source=args.source_line,
        transfer=args.transfer,
    )
    for path in track_paths:
        print(path)
    print(paths["txt"])
    print(paths["ffp"])
    print(f"packaged {len(track_paths)} tracks → {out_dir}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
