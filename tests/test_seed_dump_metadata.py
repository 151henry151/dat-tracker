"""Integration: seed_package_metadata fills dump shows from path + jcard hooks."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from dat_tracker.review_hydrate import seed_package_metadata
from dat_tracker.review_plan import empty_package_fields, migrate_tracking_plan


def _bare_plan(show_id: str, source_path: str) -> dict:
    return migrate_tracking_plan(
        {
            "schema_version": "1.0.0",
            "show_id": show_id,
            "source_path": source_path,
            "duration_sec": 10.0,
            "cuts_sec": [0.0, 10.0],
            "tracks": [
                {
                    "index": 1,
                    "start_sec": 0.0,
                    "end_sec": 10.0,
                    "track_type": "song",
                    "title": "A",
                    "segue_into_next": False,
                    "confidence": 0.5,
                    "evidence": [],
                }
            ],
            "notes": [],
            "overall_confidence": 0.5,
            "needs_review": False,
        }
    )


def test_seed_fills_from_dump_path_without_companions(tmp_path: Path):
    dump = tmp_path / "dump"
    flac = (
        dump
        / "Brian H Flacs Wave 2"
        / "Huck Finn Festival - April 2003"
        / "06132003_HF_01-McNasty→Shiflett→BGBrethren.flac"
    )
    flac.parent.mkdir(parents=True)
    flac.write_bytes(b"f")
    (tmp_path / "catalog").mkdir()
    (tmp_path / "catalog" / "shows.json").write_text(
        json.dumps({"schema_version": "1.0.0", "shows": []})
    )

    plan = _bare_plan(flac.stem, str(flac))
    assert plan["package"]["artist"] is None

    with patch(
        "dat_tracker.review_package_extract.companion_extract_for_show",
        return_value={},
    ), patch(
        "dat_tracker.jcard_extract.jcard_extract_for_audio",
        return_value={},
    ):
        out = seed_package_metadata(
            plan,
            project_root=tmp_path,
            source_audio=flac,
            dump_root=dump,
            use_llm_extract=False,
            allow_web_research=False,
        )

    pkg = out["package"]
    assert pkg["date"] == "2003-06-13"
    assert pkg["venue"] == "Huck Finn Festival"
    assert "McNasty" in pkg["artist"]
    assert "Bluegrass Brethren" in pkg["artist"]
    assert pkg["collection_subjects"] == ["Brian H Collection"]
    assert pkg["transferer"] == "Cate Crowe"


def test_seed_prefers_jcard_over_filename_artist(tmp_path: Path):
    dump = tmp_path / "dump"
    flac = (
        dump
        / "Brian H Flacs Wave 2"
        / "Huck Finn Festival - April 2003"
        / "06132003_HF_01-McNasty→Shiflett→BGBrethren.flac"
    )
    flac.parent.mkdir(parents=True)
    flac.write_bytes(b"f")
    (tmp_path / "catalog").mkdir()
    (tmp_path / "catalog" / "shows.json").write_text(
        json.dumps({"schema_version": "1.0.0", "shows": []})
    )
    plan = _bare_plan(flac.stem, str(flac))

    with patch(
        "dat_tracker.review_package_extract.companion_extract_for_show",
        return_value={},
    ), patch(
        "dat_tracker.jcard_extract.jcard_extract_for_audio",
        return_value={
            "artist": "McNasty > Bluegrass Brethren",
            "date": "2003-06-13",
            "notes": "DAT 1; BH",
        },
    ):
        out = seed_package_metadata(
            plan,
            project_root=tmp_path,
            source_audio=flac,
            dump_root=dump,
            use_llm_extract=True,
            allow_web_research=False,
        )

    assert out["package"]["artist"] == "McNasty > Bluegrass Brethren"
    assert "DAT 1" in (out["package"].get("notes") or "")
    assert any("J-card" in str(n) for n in (out.get("notes") or []))


def test_seed_cli_artist_wins(tmp_path: Path):
    flac = tmp_path / "x.flac"
    flac.write_bytes(b"f")
    (tmp_path / "catalog").mkdir()
    (tmp_path / "catalog" / "shows.json").write_text(
        json.dumps({"schema_version": "1.0.0", "shows": []})
    )
    plan = _bare_plan("06132003_HF_01-McNasty→Shiflett→BGBrethren", str(flac))
    with patch(
        "dat_tracker.review_package_extract.companion_extract_for_show",
        return_value={},
    ), patch(
        "dat_tracker.jcard_extract.jcard_extract_for_audio",
        return_value={"artist": "From Jcard"},
    ):
        out = seed_package_metadata(
            plan,
            project_root=tmp_path,
            source_audio=flac,
            artist="Explicit Artist",
            use_llm_extract=True,
            allow_web_research=False,
        )
    assert out["package"]["artist"] == "Explicit Artist"


def test_seed_replaces_unknown_artist_and_epoch_date(tmp_path: Path):
    """Dump-track placeholders must not block filename heuristics."""
    dump = tmp_path / "dump"
    flac = (
        dump
        / "Brian H Flacs Wave 2"
        / "Huck Finn Festival - April 2003"
        / "06132003_HF_01-McNasty→Shiflett→BGBrethren.flac"
    )
    flac.parent.mkdir(parents=True)
    flac.write_bytes(b"f")
    (tmp_path / "catalog").mkdir()
    (tmp_path / "catalog" / "shows.json").write_text(
        json.dumps({"schema_version": "1.0.0", "shows": []})
    )
    plan = _bare_plan(flac.stem, str(flac))
    plan["package"]["artist"] = "Unknown Artist"
    plan["package"]["date"] = "1970-01-01"

    with patch(
        "dat_tracker.review_package_extract.companion_extract_for_show",
        return_value={},
    ), patch(
        "dat_tracker.jcard_extract.jcard_extract_for_audio",
        return_value={},
    ):
        out = seed_package_metadata(
            plan,
            project_root=tmp_path,
            source_audio=flac,
            dump_root=dump,
            artist="Unknown Artist",
            date="1970-01-01",
            use_llm_extract=False,
            allow_web_research=False,
        )

    pkg = out["package"]
    assert pkg["date"] == "2003-06-13"
    assert "McNasty" in pkg["artist"]
    assert pkg["venue"] == "Huck Finn Festival"
