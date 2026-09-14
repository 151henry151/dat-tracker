"""Discover continuous FLACs under a dump directory for dat-review."""

from __future__ import annotations

import json
from pathlib import Path

from dat_tracker.catalog_io import write_catalog
from dat_tracker.dump_discover import (
    default_dump_root,
    discover_dump_shows,
    show_id_for_flac,
)


def _write_plan(path: Path, *, show_id: str, source: str, status: str = "pending") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": "1.1.0",
                "show_id": show_id,
                "source_path": source,
                "duration_sec": 120.0,
                "cuts_sec": [0.0, 60.0, 120.0],
                "tracks": [
                    {
                        "index": 1,
                        "start_sec": 0.0,
                        "end_sec": 60.0,
                        "track_type": "song",
                        "title": "A",
                        "segue_into_next": False,
                        "confidence": 0.8,
                        "evidence": [],
                    },
                    {
                        "index": 2,
                        "start_sec": 60.0,
                        "end_sec": 120.0,
                        "track_type": "song",
                        "title": "B",
                        "segue_into_next": False,
                        "confidence": 0.8,
                        "evidence": [],
                    },
                ],
                "overall_confidence": 0.8,
                "needs_review": False,
                "notes": [],
                "package": {},
                "review": {
                    "status": status,
                    "approved_at": None,
                    "approved_by": None,
                    "method": None,
                },
            }
        )
        + "\n"
    )


def test_show_id_prefers_catalog_raw_path(tmp_path: Path):
    dump = tmp_path / "extracted"
    flac = dump / "Dave W Flacs" / "800913_Rowan_and_Logan.flac"
    flac.parent.mkdir(parents=True)
    flac.write_bytes(b"f")
    write_catalog(
        tmp_path / "catalog",
        [
            {
                "id": "800913_Rowan_and_Logan",
                "raw_path": "Dave W Flacs/800913_Rowan_and_Logan.flac",
                "artist": "Rowan and Logan",
                "date": "1980-09-13",
                "status": "todo",
            }
        ],
    )
    assert (
        show_id_for_flac(
            flac,
            dump_root=dump,
            catalog_dir=tmp_path / "catalog",
        )
        == "800913_Rowan_and_Logan"
    )


def test_show_id_falls_back_to_stem(tmp_path: Path):
    dump = tmp_path / "dump"
    flac = dump / "misc" / "My_Show.flac"
    flac.parent.mkdir(parents=True)
    flac.write_bytes(b"f")
    assert show_id_for_flac(flac, dump_root=dump, catalog_dir=tmp_path / "catalog") == "My_Show"


def test_discover_dump_shows_untracked_and_linked(tmp_path: Path):
    root = tmp_path
    dump = root / "data" / "raw" / "extracted"
    a = dump / "Dave W Flacs" / "aaa.flac"
    b = dump / "Brian H Flacs" / "bbb.flac"
    a.parent.mkdir(parents=True)
    b.parent.mkdir(parents=True)
    a.write_bytes(b"a")
    b.write_bytes(b"b")
    write_catalog(
        root / "catalog",
        [
            {
                "id": "aaa",
                "raw_path": "Dave W Flacs/aaa.flac",
                "artist": "A",
                "date": "2000-01-01",
                "status": "todo",
            },
            {
                "id": "bbb",
                "raw_path": "Brian H Flacs/bbb.flac",
                "artist": "B",
                "date": "2001-01-01",
                "status": "todo",
            },
        ],
    )
    _write_plan(
        root / "data" / "work" / "bbb" / "tracking_plan_gemini.json",
        show_id="bbb",
        source=str(b),
        status="pending",
    )

    shows = discover_dump_shows(dump, project_root=root)
    by_id = {s.show_id: s for s in shows}
    assert set(by_id) == {"aaa", "bbb"}
    assert by_id["aaa"].needs_tracking is True
    assert by_id["aaa"].review_status == "untracked"
    assert by_id["aaa"].source_path == a
    assert by_id["aaa"].has_audio is True
    assert by_id["bbb"].needs_tracking is False
    assert by_id["bbb"].review_status == "pending"
    assert by_id["bbb"].track_count == 2
    assert by_id["bbb"].plan_path.is_file()


def test_discover_links_plan_by_source_path_even_if_show_id_differs(tmp_path: Path):
    root = tmp_path
    dump = root / "dump"
    flac = dump / "x.flac"
    flac.parent.mkdir(parents=True)
    flac.write_bytes(b"x")
    _write_plan(
        root / "data" / "work" / "other-id" / "tracking_plan_gemini.json",
        show_id="other-id",
        source=str(flac.resolve()),
        status="approved",
    )
    shows = discover_dump_shows(dump, project_root=root)
    assert len(shows) == 1
    assert shows[0].show_id == "other-id"
    assert shows[0].review_status == "approved"
    assert shows[0].needs_tracking is False


def test_default_dump_root_prefers_extracted_with_flacs(tmp_path: Path):
    extracted = tmp_path / "data" / "raw" / "extracted" / "Dave W Flacs"
    extracted.mkdir(parents=True)
    (extracted / "one.flac").write_bytes(b"1")
    assert default_dump_root(tmp_path, use_last=False) == tmp_path / "data" / "raw" / "extracted"


def test_default_dump_root_none_when_empty(tmp_path: Path):
    (tmp_path / "data" / "raw" / "extracted").mkdir(parents=True)
    assert default_dump_root(tmp_path, use_last=False) is None
