"""Tests for companion/catalog resolution used when seeding review metadata."""

from __future__ import annotations

import json
from pathlib import Path

from dat_tracker.review_hydrate import (
    find_companion_show_txt,
    hydrate_titles_from_published_setlist,
    lookup_catalog_show,
    resolve_companion_dirs,
    seed_package_metadata,
)
from dat_tracker.review_plan import migrate_tracking_plan
from dat_tracker.tracking_plan import validate_tracking_plan


def test_resolve_companion_dirs_prefers_calibration_then_ground_truth(tmp_path: Path):
    show_id = "jmp2002-11-15"
    cal = tmp_path / "data" / "calibration" / show_id
    gt = tmp_path / "data" / "ground_truth" / show_id
    gt.mkdir(parents=True)
    (gt / "show.txt").write_text("Artist\nVenue\nTown, CA\n2002-11-15\n")
    dirs = resolve_companion_dirs(show_id, project_root=tmp_path)
    assert dirs == [gt]

    cal.mkdir(parents=True)
    (cal / "info.txt").write_text("Cal Artist\n")
    dirs = resolve_companion_dirs(show_id, project_root=tmp_path)
    assert dirs[0] == cal
    assert gt in dirs


def test_lookup_catalog_show_reads_shows_json(tmp_path: Path):
    cat = tmp_path / "catalog"
    cat.mkdir()
    (cat / "shows.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0.0",
                "shows": [
                    {
                        "id": "jmp2002-11-15",
                        "artist": "Jazz Mandolin Project",
                        "date": "2002-11-15",
                        "venue": "Winston's",
                        "city": "San Diego",
                        "state": "CA",
                        "collection": "Brian H Collection",
                    }
                ],
            }
        )
    )
    row = lookup_catalog_show("jmp2002-11-15", project_root=tmp_path)
    assert row is not None
    assert row["artist"] == "Jazz Mandolin Project"
    assert row["venue"] == "Winston's"


def test_seed_and_titles_from_ground_truth(tmp_path: Path):
    show_id = "jmp2002-11-15"
    gt = tmp_path / "data" / "ground_truth" / show_id
    gt.mkdir(parents=True)
    (gt / f"{show_id}.txt").write_text(
        "Jazz Mandolin Project\n"
        "November 15, 2002 (2002-11-15)\n"
        "Winston's\n"
        "San Diego, CA\n"
        "\n"
        "Source: AUD > DAT\n"
        "Transfer: DAT > FLAC\n"
        "Transferred by: Cate Crowe\n"
        "\n"
        "One Set:\n"
        "1. Mariachi Song\n"
        "2. Open Sesame >\n"
        "3. Dimensions\n"
    )
    plan = migrate_tracking_plan(
        {
            "schema_version": "1.0.0",
            "show_id": show_id,
            "source_path": "x.flac",
            "duration_sec": 300.0,
            "cuts_sec": [0.0, 100.0, 200.0, 300.0],
            "tracks": [
                {
                    "index": i,
                    "start_sec": float((i - 1) * 100),
                    "end_sec": float(i * 100),
                    "track_type": "unknown",
                    "title": None,
                    "segue_into_next": False,
                    "confidence": 0.5,
                    "evidence": [],
                }
                for i in range(1, 4)
            ],
            "overall_confidence": 0.5,
            "needs_review": False,
            "notes": [],
        }
    )
    assert find_companion_show_txt(show_id, project_root=tmp_path) is not None
    plan = hydrate_titles_from_published_setlist(plan, project_root=tmp_path)
    plan = seed_package_metadata(plan, project_root=tmp_path, use_llm_extract=False)
    assert plan["package"]["artist"] == "Jazz Mandolin Project"
    assert plan["package"]["venue"] == "Winston's"
    assert plan["package"]["city"] == "San Diego"
    assert plan["package"]["state"] == "CA"
    assert plan["package"]["source"] == "AUD > DAT"
    assert plan["package"]["transfer"] == "DAT > FLAC"
    assert plan["package"]["transferer"] == "Cate Crowe"
    titles = [t.get("title") for t in plan["tracks"]]
    assert titles[0] == "Mariachi Song"
    assert "Open Sesame" in (titles[1] or "")
    validate_tracking_plan(plan)
