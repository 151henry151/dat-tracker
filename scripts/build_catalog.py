#!/usr/bin/env python3
"""Build catalog/shows.{json,csv} from IA search (+ optional Dropbox zip listing)."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dat_tracker.catalog_ia import shows_from_ia_response
from dat_tracker.catalog_io import write_catalog
from dat_tracker.catalog_merge import merge_catalog
from dat_tracker.catalog_raw import parse_zip_listing_line, shows_from_zip_paths

IA_QUERIES = [
    'subject:"Dave Ward Collection" OR subject:"Dave Ward collection"',
    'subject:"Brian H Collection"',
]
EXPECTED_ZIP_BYTES = 107_045_111_705


def fetch_ia_shows() -> list[dict]:
    shows: list[dict] = []
    for query in IA_QUERIES:
        params = urllib.parse.urlencode(
            {
                "q": query,
                "fl[]": [
                    "identifier",
                    "title",
                    "creator",
                    "date",
                    "venue",
                    "coverage",
                    "collection",
                    "subject",
                ],
                "rows": "100",
                "page": "1",
                "output": "json",
            },
            doseq=True,
        )
        url = f"https://archive.org/advancedsearch.php?{params}"
        with urllib.request.urlopen(url, timeout=60) as resp:
            payload = json.load(resp)
        shows.extend(shows_from_ia_response(payload))
    # De-dupe by identifier.
    by_id = {s["id"]: s for s in shows}
    return list(by_id.values())


def zip_paths(zip_path: Path) -> list[str]:
    proc = subprocess.run(
        ["unzip", "-l", str(zip_path)],
        check=True,
        capture_output=True,
        text=True,
    )
    paths: list[str] = []
    for line in proc.stdout.splitlines():
        path = parse_zip_listing_line(line)
        if path and not path.endswith("/"):
            paths.append(path)
    return paths


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--zip",
        type=Path,
        default=ROOT / "data" / "raw" / "Live Bluegrass.zip",
        help="Dropbox dump zip (used only if present and complete)",
    )
    parser.add_argument(
        "--catalog-dir",
        type=Path,
        default=ROOT / "catalog",
    )
    parser.add_argument(
        "--require-zip",
        action="store_true",
        help="Fail if the Dropbox zip is missing or incomplete",
    )
    args = parser.parse_args()

    ia_shows = fetch_ia_shows()
    print(f"IA already-uploaded items: {len(ia_shows)}")

    raw_shows: list[dict] = []
    zip_path: Path = args.zip
    if zip_path.is_file():
        size = zip_path.stat().st_size
        if size == EXPECTED_ZIP_BYTES:
            paths = zip_paths(zip_path)
            raw_shows = shows_from_zip_paths(paths)
            print(f"Raw FLAC candidates from zip: {len(raw_shows)} (of {len(paths)} entries)")
        else:
            msg = (
                f"Zip present but incomplete: {size} / {EXPECTED_ZIP_BYTES} bytes "
                f"({100.0 * size / EXPECTED_ZIP_BYTES:.2f}%)"
            )
            if args.require_zip:
                print(msg, file=sys.stderr)
                return 1
            print(msg + "; writing IA-only catalog for now")
    elif args.require_zip:
        print(f"Missing zip: {zip_path}", file=sys.stderr)
        return 1
    else:
        print(f"No zip at {zip_path}; writing IA-only catalog for now")

    merged = merge_catalog(raw_shows=raw_shows, ia_shows=ia_shows)
    write_catalog(args.catalog_dir, merged)
    uploaded = sum(1 for s in merged if s["status"] == "already_uploaded")
    todo = sum(1 for s in merged if s["status"] == "todo")
    print(f"Wrote {len(merged)} shows -> {args.catalog_dir}/shows.json")
    print(f"  already_uploaded={uploaded} todo={todo}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
