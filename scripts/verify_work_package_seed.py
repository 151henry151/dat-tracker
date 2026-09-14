#!/usr/bin/env python3
"""Seed package metadata for every data/work show and report blank fields.

Uses the LLM companion extract path (and optional Google Search research for
missing venue/city/state). Requires GEMINI_API_KEY.

Example:
  uv run python scripts/verify_work_package_seed.py
  uv run python scripts/verify_work_package_seed.py --no-web-research
  uv run python scripts/verify_work_package_seed.py --show jmp2002-11-15
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dat_tracker.review_discover import prefer_plan_path  # noqa: E402
from dat_tracker.review_hydrate import (  # noqa: E402
    find_companion_show_txt,
    hydrate_plan_from_companions,
    hydrate_plan_from_notes,
)
from dat_tracker.review_package_polish import polish_package_metadata  # noqa: E402
from dat_tracker.review_plan import migrate_tracking_plan  # noqa: E402

REQUIRED = ("artist", "date", "venue", "city", "state", "source", "transfer")


def _stub_plan(show_id: str) -> dict:
    return migrate_tracking_plan(
        {
            "schema_version": "1.0.0",
            "show_id": show_id,
            "source_path": "x.flac",
            "duration_sec": 100.0,
            "cuts_sec": [0.0, 100.0],
            "tracks": [
                {
                    "index": 1,
                    "start_sec": 0.0,
                    "end_sec": 100.0,
                    "track_type": "unknown",
                    "title": None,
                    "segue_into_next": False,
                    "confidence": 0.5,
                    "evidence": [],
                }
            ],
            "overall_confidence": 0.5,
            "needs_review": False,
            "notes": [],
            "package": {},
        }
    )


def _seed_show(
    show_dir: Path,
    *,
    allow_web_research: bool,
) -> dict:
    show_id = show_dir.name
    plan_path = prefer_plan_path(show_dir)
    if plan_path is not None:
        raw = json.loads(plan_path.read_text())
        raw = dict(raw)
        raw["package"] = {}
        # Allow a fresh LLM extract on this verification run.
        raw["notes"] = [
            n
            for n in (raw.get("notes") or [])
            if "Extracted package metadata" not in str(n)
            and "Researched missing package" not in str(n)
        ]
        plan = migrate_tracking_plan(raw)
    else:
        plan = _stub_plan(show_id)
    plan = hydrate_plan_from_notes(plan)
    plan = hydrate_plan_from_companions(
        plan,
        project_root=ROOT,
        use_llm=True,
        allow_web_research=allow_web_research,
    )
    return polish_package_metadata(plan, project_root=ROOT, use_llm=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--show",
        action="append",
        dest="shows",
        help="Limit to one or more show ids (repeatable)",
    )
    parser.add_argument(
        "--no-web-research",
        action="store_true",
        help="Disable Google Search grounding for missing location fields",
    )
    args = parser.parse_args()
    work = ROOT / "data" / "work"
    if not work.is_dir():
        print(f"missing {work}", file=sys.stderr)
        return 2

    dirs = sorted(
        p for p in work.iterdir() if p.is_dir() and not p.name.startswith(".")
    )
    if args.shows:
        wanted = set(args.shows)
        dirs = [p for p in dirs if p.name in wanted]

    failures = 0
    for show_dir in dirs:
        companion = find_companion_show_txt(show_dir.name, project_root=ROOT)
        if companion is None:
            print(f"{show_dir.name:40} SKIP  no companion txt")
            continue
        print(f"{show_dir.name:40} seeding…", flush=True)
        try:
            plan = _seed_show(
                show_dir,
                allow_web_research=not args.no_web_research,
            )
        except Exception as exc:  # noqa: BLE001 — report and continue
            failures += 1
            print(f"{show_dir.name:40} ERROR {exc}")
            continue
        pkg = plan.get("package") or {}
        blank = [k for k in REQUIRED if not pkg.get(k)]
        titled = sum(1 for t in plan.get("tracks") or [] if t.get("title"))
        status = "OK" if not blank else "BLANK"
        if blank:
            failures += 1
        print(
            f"{show_dir.name:40} {status:5} blank={blank or '-'} "
            f"titled={titled} companion={companion.name}"
        )
        print(
            "   "
            + " | ".join(f"{k}={pkg.get(k)!r}" for k in REQUIRED + ("transferer",))
        )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
