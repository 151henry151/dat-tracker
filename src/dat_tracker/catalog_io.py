"""Read/write catalog/shows.json and catalog/shows.csv."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0.0"
CSV_FIELDS = [
    "id",
    "raw_path",
    "artist",
    "date",
    "venue",
    "city",
    "state",
    "collection",
    "status",
    "ia_identifier",
    "ia_collection",
    "source",
    "notes",
]


def catalog_document(shows: list[dict[str, Any]]) -> dict[str, Any]:
    return {"schema_version": SCHEMA_VERSION, "shows": shows}


def shows_from_catalog(doc: dict[str, Any]) -> list[dict[str, Any]]:
    return list(doc.get("shows") or [])


def catalog_to_csv(shows: list[dict[str, Any]]) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=CSV_FIELDS, extrasaction="ignore")
    writer.writeheader()
    for show in shows:
        row = {field: show.get(field) if show.get(field) is not None else "" for field in CSV_FIELDS}
        writer.writerow(row)
    return buf.getvalue()


def write_catalog(catalog_dir: Path, shows: list[dict[str, Any]]) -> None:
    catalog_dir.mkdir(parents=True, exist_ok=True)
    doc = catalog_document(shows)
    (catalog_dir / "shows.json").write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    (catalog_dir / "shows.csv").write_text(catalog_to_csv(shows), encoding="utf-8")


def load_catalog(catalog_dir: Path) -> list[dict[str, Any]]:
    path = catalog_dir / "shows.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    return shows_from_catalog(doc)
