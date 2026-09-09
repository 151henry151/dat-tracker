#!/usr/bin/env python3
"""Prepare Tier A continuous extracts (aligned raw span + known_cuts) for scoring."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dat_tracker.tier_a import prepare_tier_a_continuous, resolve_raw_flac_path  # noqa: E402


def _raw_paths_for_show(row: dict) -> list[str]:
    rp = row.get("raw_path") or ""
    return [ln.strip() for ln in str(rp).splitlines() if ln.strip().endswith(".flac")]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--catalog",
        type=Path,
        default=ROOT / "catalog" / "shows.json",
    )
    parser.add_argument(
        "--show-id",
        action="append",
        dest="ids",
        default=None,
        help="Limit to these catalog ids (repeatable). Default: all already_uploaded with raw_path",
    )
    parser.add_argument(
        "--extracted-root",
        type=Path,
        default=ROOT / "data" / "raw" / "extracted",
    )
    parser.add_argument(
        "--out-root",
        type=Path,
        default=ROOT / "data" / "calibration_tier_a",
    )
    parser.add_argument("--snippet-duration", type=float, default=45.0)
    args = parser.parse_args()

    shows = json.loads(args.catalog.read_text())["shows"]
    rows = [
        s
        for s in shows
        if s.get("status") == "already_uploaded" and _raw_paths_for_show(s)
    ]
    if args.ids:
        want = set(args.ids)
        rows = [s for s in rows if s["id"] in want]

    failures: list[str] = []
    for row in rows:
        show_id = str(row["id"])
        raw_members = _raw_paths_for_show(row)
        # Prefer a single continuous raw; for multipart take part 1 for now.
        raw_member = raw_members[0]
        try:
            raw = resolve_raw_flac_path(
                project_root=ROOT,
                raw_path=raw_member,
                extracted_root=args.extracted_root,
            )
        except FileNotFoundError as exc:
            print(f"SKIP {show_id}: {exc}", file=sys.stderr)
            failures.append(show_id)
            continue
        gt = ROOT / "data" / "ground_truth" / show_id
        if not gt.is_dir():
            # IA id may differ slightly from catalog id.
            ia = row.get("ia_identifier") or show_id
            gt = ROOT / "data" / "ground_truth" / str(ia)
        if not gt.is_dir():
            print(f"SKIP {show_id}: missing ground_truth {gt}", file=sys.stderr)
            failures.append(show_id)
            continue
        out_dir = args.out_root / show_id
        print(f"PREPARE {show_id} from {raw.name} ...", flush=True)
        try:
            meta = prepare_tier_a_continuous(
                show_id=show_id,
                raw_flac=raw,
                ground_truth_dir=gt,
                out_dir=out_dir,
                snippet_duration_sec=args.snippet_duration,
            )
        except Exception as exc:  # noqa: BLE001 — report and continue batch
            print(f"FAIL {show_id}: {exc}", file=sys.stderr)
            failures.append(show_id)
            continue
        print(
            f"OK {show_id} offset={meta['align_offset_sec']:.1f}s "
            f"dist={meta['align_distance']:.3f} "
            f"dur={meta['extract_duration_sec']:.1f}s",
            flush=True,
        )

    if failures:
        print("failures:", ", ".join(failures), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
