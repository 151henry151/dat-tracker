"""Tests for hydrating blank LLM track titles/types from listen notes."""

from pathlib import Path

from dat_tracker.review_hydrate import (
    hydrate_plan_from_notes,
    parse_published_show_txt,
    seed_package_metadata,
)
from dat_tracker.review_plan import migrate_tracking_plan
from dat_tracker.tracking_plan import validate_tracking_plan


def _sbb_like_plan():
    return migrate_tracking_plan(
        {
            "schema_version": "1.0.0",
            "show_id": "sbb2001-04-27.flac16",
            "source_path": "data/calibration/sbb2001-04-27.flac16/synthetic_continuous.flac",
            "duration_sec": 1210.24,
            "cuts_sec": [0.0, 375.3, 536.4, 645.0, 1210.24],
            "tracks": [
                {
                    "index": 1,
                    "start_sec": 0.0,
                    "end_sec": 375.3,
                    "track_type": "unknown",
                    "title": None,
                    "segue_into_next": False,
                    "confidence": 0.5,
                    "evidence": [],
                },
                {
                    "index": 2,
                    "start_sec": 375.3,
                    "end_sec": 536.4,
                    "track_type": "unknown",
                    "title": None,
                    "segue_into_next": False,
                    "confidence": 0.5,
                    "evidence": [],
                },
                {
                    "index": 3,
                    "start_sec": 536.4,
                    "end_sec": 645.0,
                    "track_type": "unknown",
                    "title": None,
                    "segue_into_next": False,
                    "confidence": 0.5,
                    "evidence": [],
                },
                {
                    "index": 4,
                    "start_sec": 645.0,
                    "end_sec": 1210.24,
                    "track_type": "unknown",
                    "title": None,
                    "segue_into_next": False,
                    "confidence": 0.5,
                    "evidence": [],
                },
            ],
            "overall_confidence": 0.5,
            "needs_review": False,
            "notes": [
                "REJECT 112.940s: continuous music ('Girl from the North Country').",
                "REJECT 277.000s: continuous music ('Girl from the North Country').",
                "SNAP 375.340s -> 379.000s: song 1 ends around 363s; spoken intro ends and second song rhythm starts at 379.0s.",
                "SNAP 536.380s -> 524.000s: song 2 finishes around 524.0s with applause and transition into stage banter.",
                "REJECT 581.800s: mid-banter joke inside extended stage break.",
                "SNAP 644.920s -> 648.000s: stage banter ends and song 3 intro starts at 648.0s.",
                "REJECT 737.000s: continuous music ('Sailin' Shoes' / 'Cocaine').",
                "REJECT 869.000s: continuous music ('Doctor Doctor').",
                "REJECT 992.000s: continuous music ('Sun's Going Down').",
                "Materialized tracks from cuts_sec (model returned empty tracks).",
            ],
        }
    )


def test_hydrate_fills_titles_and_banter_from_notes():
    plan = hydrate_plan_from_notes(_sbb_like_plan())
    validate_tracking_plan(plan)
    assert plan["tracks"][0]["title"] == "Girl from the North Country"
    assert plan["tracks"][0]["track_type"] == "song"
    # Track 3 is the banter island between song 2 and song 3 starts.
    assert plan["tracks"][2]["track_type"] == "banter"
    assert plan["tracks"][3]["title"] in {
        "Sailin' Shoes' / 'Cocaine",
        "Sailin' Shoes / Cocaine",
        "Doctor Doctor",
        "Sun's Going Down",
    }
    # Prefer first named continuous-music title in the span.
    assert "Sailin" in (plan["tracks"][3]["title"] or "")


def test_hydrate_parses_legacy_time_first_notes():
    """Older Gemini dumps used ``112.94s: REJECT - continuous music/singing (Title).``"""
    plan = _sbb_like_plan()
    plan["notes"] = [
        "112.94s: REJECT - continuous music/singing (Girl From The North Country).",
        "375.34s: SNAP to 367.00s - previous song finishes into applause, stage banter onset at ~367s.",
        "468.00s: REJECT - continuous fast banjo instrumental solo.",
        "536.38s: SNAP to 530.00s - banjo instrumental ends ~525s, banter onset at ~530s.",
        "581.80s: REJECT - continuous stage banter ('Amway...').",
        "644.92s: SNAP to 649.00s - banter ends and next song count-in/first notes start at ~649s.",
        "737.00s: REJECT - continuous music (Sailing Shoes / Cocaine Blues).",
    ]
    out = hydrate_plan_from_notes(plan)
    assert out["tracks"][0]["title"] == "Girl From The North Country"
    assert out["tracks"][0]["track_type"] == "song"
    # SNAP text about banter onset at the cut must not flip the following song.
    assert out["tracks"][1]["track_type"] == "song"
    assert out["tracks"][2]["track_type"] == "banter"
    assert out["tracks"][2]["title"] == "Banter"
    assert out["tracks"][3]["title"] == "Sailing Shoes / Cocaine Blues"


def test_hydrate_retypes_blank_song_to_banter_from_notes():
    """Prior hydrate stamped long blanks as song; reopen should still learn banter."""
    plan = _sbb_like_plan()
    plan["tracks"][2]["track_type"] = "song"
    plan["tracks"][2]["title"] = None
    plan["tracks"][2]["evidence"] = ["hydrated_from_notes"]
    out = hydrate_plan_from_notes(plan)
    assert out["tracks"][2]["track_type"] == "banter"
    assert out["tracks"][2]["title"] == "Banter"


def test_hydrate_does_not_title_banter_from_song_notes():
    plan = _sbb_like_plan()
    plan["tracks"][0]["track_type"] = "song"
    plan["tracks"][0]["title"] = "Girl from the North Country"
    # Split-like banter island that still overlaps a continuous-music note time.
    plan["tracks"][1]["track_type"] = "banter"
    plan["tracks"][1]["title"] = None
    plan["tracks"][1]["start_sec"] = 250.0
    plan["tracks"][1]["end_sec"] = 375.3
    out = hydrate_plan_from_notes(plan)
    assert out["tracks"][1]["track_type"] == "banter"
    # Jon/etree style: blank banter gets the literal title "Banter", not a song name.
    assert out["tracks"][1].get("title") == "Banter"


def test_hydrate_fills_type_default_titles():
    plan = _sbb_like_plan()
    plan["tracks"][2]["track_type"] = "banter"
    plan["tracks"][2]["title"] = None
    plan["notes"] = [
        "REJECT 581.800s: mid-banter joke inside extended stage break.",
    ]
    out = hydrate_plan_from_notes(plan)
    assert out["tracks"][2]["title"] == "Banter"


def test_reconcile_merges_surplus_short_track_to_match_setlist(tmp_path: Path):
    from dat_tracker.review_hydrate import reconcile_track_count_to_published_setlist

    cal = tmp_path / "data" / "calibration" / "demo.flac16"
    cal.mkdir(parents=True)
    (cal / "info.txt").write_text(
        "Band\nTown, MO\n2002-08-30\n\n"
        "Set I\n"
        "01 Song A\n"
        "02 Song B\n"
        "03 Song C\n"
    )
    # 4 tracks but setlist has 3 — short middle island should merge away.
    plan = migrate_tracking_plan(
        {
            "schema_version": "1.0.0",
            "show_id": "demo.flac16",
            "source_path": "x.flac",
            "duration_sec": 400.0,
            "cuts_sec": [0.0, 100.0, 150.0, 200.0, 400.0],
            "tracks": [
                {
                    "index": 1,
                    "start_sec": 0.0,
                    "end_sec": 100.0,
                    "track_type": "song",
                    "title": None,
                    "segue_into_next": False,
                    "confidence": 0.5,
                    "evidence": [],
                },
                {
                    "index": 2,
                    "start_sec": 100.0,
                    "end_sec": 150.0,
                    "track_type": "unknown",
                    "title": None,
                    "segue_into_next": False,
                    "confidence": 0.5,
                    "evidence": [],
                },
                {
                    "index": 3,
                    "start_sec": 150.0,
                    "end_sec": 200.0,
                    "track_type": "song",
                    "title": None,
                    "segue_into_next": False,
                    "confidence": 0.5,
                    "evidence": [],
                },
                {
                    "index": 4,
                    "start_sec": 200.0,
                    "end_sec": 400.0,
                    "track_type": "song",
                    "title": None,
                    "segue_into_next": False,
                    "confidence": 0.5,
                    "evidence": [],
                },
            ],
            "overall_confidence": 0.5,
            "needs_review": False,
            "notes": [],
        }
    )
    out = reconcile_track_count_to_published_setlist(plan, project_root=tmp_path)
    assert len(out["tracks"]) == 3
    assert len(out["cuts_sec"]) == 4
    # Short island 100–150 merged into a neighbor; no 50s fragment left.
    spans = [
        float(t["end_sec"]) - float(t["start_sec"]) for t in out["tracks"]
    ]
    assert min(spans) >= 50.0 - 1e-6
    assert any(
        "Reconciled track count" in str(n) for n in out["notes"]
    )


def test_parse_published_setlist_cornmeal_shape(tmp_path: Path):
    from dat_tracker.review_hydrate import parse_published_setlist

    txt = tmp_path / "show.txt"
    txt.write_text(
        "Cornmeal\n"
        "Venue: Somewhere\n"
        "Lesterville, MO\n"
        "08-30-2002\n"
        "\n"
        "Set I\n"
        "\n"
        "01 Blue Line Express\n"
        "02 Yesterday Morning\n"
        "03 Long Gone\n"
        "04 Salty Dog Blues\n"
    )
    assert parse_published_setlist(txt) == [
        "Blue Line Express",
        "Yesterday Morning",
        "Long Gone",
        "Salty Dog Blues",
    ]


def test_hydrate_titles_from_published_setlist(tmp_path: Path):
    from dat_tracker.review_hydrate import hydrate_titles_from_published_setlist

    cal = tmp_path / "data" / "calibration" / "crnml2002-08-30.flac16"
    cal.mkdir(parents=True)
    (cal / "info.txt").write_text(
        "Cornmeal\n"
        "Lesterville, MO\n"
        "2002-08-30\n"
        "\n"
        "Set I\n"
        "01 Blue Line Express\n"
        "02 Yesterday Morning\n"
        "03 Long Gone\n"
    )
    plan = migrate_tracking_plan(
        {
            "schema_version": "1.0.0",
            "show_id": "crnml2002-08-30.flac16",
            "source_path": "x.flac",
            "duration_sec": 900.0,
            "cuts_sec": [0.0, 100.0, 200.0, 250.0, 900.0],
            "tracks": [
                {
                    "index": 1,
                    "start_sec": 0.0,
                    "end_sec": 100.0,
                    "track_type": "song",
                    "title": None,
                    "segue_into_next": False,
                    "confidence": 0.5,
                    "evidence": [],
                },
                {
                    "index": 2,
                    "start_sec": 100.0,
                    "end_sec": 200.0,
                    "track_type": "song",
                    "title": None,
                    "segue_into_next": False,
                    "confidence": 0.5,
                    "evidence": [],
                },
                {
                    "index": 3,
                    "start_sec": 200.0,
                    "end_sec": 250.0,
                    "track_type": "banter",
                    "title": "Banter",
                    "segue_into_next": False,
                    "confidence": 0.5,
                    "evidence": [],
                },
                {
                    "index": 4,
                    "start_sec": 250.0,
                    "end_sec": 900.0,
                    "track_type": "song",
                    "title": None,
                    "segue_into_next": False,
                    "confidence": 0.5,
                    "evidence": [],
                },
            ],
            "overall_confidence": 0.5,
            "needs_review": False,
            "notes": [],
        }
    )
    out = hydrate_titles_from_published_setlist(plan, project_root=tmp_path)
    assert out["tracks"][0]["title"] == "Blue Line Express"
    assert out["tracks"][1]["title"] == "Yesterday Morning"
    assert out["tracks"][2]["title"] == "Banter"  # banter untouched
    assert out["tracks"][3]["title"] == "Long Gone"
    validate_tracking_plan(out)


def test_hydrate_setlist_skips_question_placeholder(tmp_path: Path):
    from dat_tracker.review_hydrate import parse_published_setlist

    txt = tmp_path / "s.txt"
    txt.write_text(
        "Artist\nVenue\nTown, NC\n2001-04-27\n\n"
        "disc 1\n"
        "01.Girl from the north country\n"
        "02.?\n"
        "03.Sailin' shoes>Crossroads\n"
    )
    assert parse_published_setlist(txt) == [
        "Girl from the north country",
        "Sailin' shoes > Crossroads",
    ]
    plan = seed_package_metadata(
        _sbb_like_plan(),
        artist="Sam Bush",
        tracker="dat-tracker",
    )
    assert plan["package"]["artist"] == "Sam Bush"
    assert plan["package"]["date"] == "2001-04-27"
    assert plan["package"]["tracker"] == "dat-tracker"
    validate_tracking_plan(plan)


def test_parse_published_show_txt_merlefest_shape(tmp_path: Path):
    txt = tmp_path / "show.txt"
    txt.write_text(
        "Sam Bush & Jerry Douglass\n"
        "Merlefest\n"
        "Wilkes Community college\n"
        "Wilkesboro,N.C.\n"
        "4-27-2001\n"
        "\n"
        "FOB Nakamichi cm700's>Sony pcm-m1 DAT master\n"
        "\n"
        "disc 1\n"
        "01.Girl from the north country\n"
    )
    fields = parse_published_show_txt(txt)
    assert fields["artist"] == "Sam Bush & Jerry Douglass"
    assert fields["venue"] == "Merlefest"
    assert "Wilkesboro" in (fields.get("city") or "")
    assert fields.get("state") in {"NC", "N.C.", "North Carolina"}
    assert fields["date"] == "2001-04-27"
    assert fields["source"] and "Nakamichi" in fields["source"]


def test_seed_package_from_published_txt(tmp_path: Path):
    cal = tmp_path / "data" / "calibration" / "sbb2001-04-27.flac16"
    cal.mkdir(parents=True)
    (cal / "info.txt").write_text(
        "Sam Bush & Jerry Douglass\n"
        "Merlefest\n"
        "Wilkesboro, NC\n"
        "2001-04-27\n"
        "\n"
        "FOB Nak > DAT\n"
    )
    # Avoid catalog; only published txt + show_id.
    plan = seed_package_metadata(
        _sbb_like_plan(),
        project_root=tmp_path,
        calibration_dir=cal,
    )
    assert plan["package"]["artist"] == "Sam Bush & Jerry Douglass"
    assert plan["package"]["venue"] == "Merlefest"
    assert plan["package"]["date"] == "2001-04-27"
    assert plan["package"]["source"] and "Nak" in plan["package"]["source"]
    validate_tracking_plan(plan)


def test_seed_package_does_not_overwrite_existing(tmp_path: Path):
    cal = tmp_path / "cal"
    cal.mkdir()
    (cal / "info.txt").write_text("Other Artist\nSome Venue\nTown, CA\n2001-04-27\n")
    plan = _sbb_like_plan()
    plan["package"]["artist"] = "Keep Me"
    plan["package"]["venue"] = "Keep Venue"
    out = seed_package_metadata(plan, project_root=tmp_path, calibration_dir=cal)
    assert out["package"]["artist"] == "Keep Me"
    assert out["package"]["venue"] == "Keep Venue"
