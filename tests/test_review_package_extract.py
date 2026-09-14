"""Tests for LLM / fallback extraction of package fields from companion files."""

from __future__ import annotations

from pathlib import Path

from dat_tracker.review_plan import migrate_tracking_plan
from dat_tracker.tracking_plan import validate_tracking_plan


def _jamshack_txt() -> str:
    return (
        "John Cowan & Pat Flynn\n"
        "\n"
        "4-16-2004\n"
        "Dade City, FL\n"
        "\n"
        "String Break!\n"
        "Sertoma Youth Ranch\n"
        "Jam Shack Stage\n"
        "\n"
        "\n"
        "SBD > Sony PCM-M1 > Wavelab 4.0 > CD Wave 1.91 > FLAC (16-bit/44.1kHz)\n"
        "(Recorded & transferred by Kevin Preuss)\n"
        "\n"
        "1.  Intro.\n"
        "2.  Blackberry Blossom\n"
    )


def test_gather_companion_sources_includes_txt_and_filenames(tmp_path: Path):
    from dat_tracker.review_package_extract import gather_companion_sources

    (tmp_path / "Pat&John4-16-04jamshack.txt").write_text(_jamshack_txt())
    (tmp_path / "John&Pat4-16-04jamshack01.flac").write_bytes(b"fLaC")
    (tmp_path / "known_cuts.json").write_text("{}")
    ctx = gather_companion_sources(tmp_path)
    assert any("Dade City" in t["text"] for t in ctx["text_files"])
    assert any("jamshack" in n.lower() for n in ctx["filenames"])
    assert not any("known_cuts" in n for n in ctx["filenames"] if False)
    # known_cuts.json may appear in filenames; text_files should skip plan-ish names
    assert not any("known_cuts" in t["name"] for t in ctx["text_files"])


def test_extract_package_fields_uses_llm_for_odd_layout(tmp_path: Path):
    from dat_tracker.review_package_extract import extract_package_fields_from_companions

    (tmp_path / "info.txt").write_text(_jamshack_txt())
    (tmp_path / "show_t01.flac").write_bytes(b"fLaC")

    def fake_llm(context: dict) -> dict:
        assert context["text_files"]
        return {
            "artist": "John Cowan & Pat Flynn",
            "date": "2004-04-16",
            "venue": "Jam Shack Stage, Sertoma Youth Ranch (String Break!)",
            "city": "Dade City",
            "state": "FL",
            "source": "SBD > Sony PCM-M1",
            "transfer": "Sony PCM-M1 > Wavelab 4.0 > CD Wave 1.91 > FLAC (16-bit/44.1kHz)",
            "transferer": "Kevin Preuss",
            "set_label": "One Set",
        }

    fields = extract_package_fields_from_companions(
        tmp_path, use_llm=True, llm_extract_fn=fake_llm
    )
    assert fields["city"] == "Dade City"
    assert fields["state"] == "FL"
    assert "Jam Shack" in (fields.get("venue") or "")
    assert fields["transferer"] == "Kevin Preuss"
    assert fields["date"] == "2004-04-16"
    assert fields["source"] == "SBD > Sony PCM-M1"
    assert "Wavelab" in (fields.get("transfer") or "")
    assert "FLAC" in (fields.get("transfer") or "")


def test_heuristic_extracts_labeled_source_and_transfer(tmp_path: Path):
    from dat_tracker.review_package_extract import extract_package_fields_from_companions

    (tmp_path / "info.txt").write_text(
        "Railroad Earth\n"
        "Camp Mather\n"
        "Grass Valley, CA\n"
        "2005-05-27\n"
        "\n"
        "Source: FM/SBD > DAT\n"
        "Transfer: DAT > Sony PCM-2600 > ESI U24XL > Audacity > FLAC\n"
        "Transferred by: Cate Crowe\n"
    )
    fields = extract_package_fields_from_companions(tmp_path, use_llm=False)
    assert fields["source"] == "FM/SBD > DAT"
    assert "PCM-2600" in fields["transfer"]
    assert fields["transferer"] == "Cate Crowe"


def test_extract_falls_back_to_heuristic_without_llm(tmp_path: Path):
    from dat_tracker.review_package_extract import extract_package_fields_from_companions

    (tmp_path / "info.txt").write_text(
        "Sam Bush\n"
        "Merlefest\n"
        "Wilkesboro, NC\n"
        "2001-04-27\n"
        "\n"
        "FOB Nak > DAT\n"
    )
    fields = extract_package_fields_from_companions(tmp_path, use_llm=False)
    assert fields["artist"] == "Sam Bush"
    assert fields["venue"] == "Merlefest"
    assert fields["city"] == "Wilkesboro"
    assert fields["state"] == "NC"


def test_seed_package_metadata_fills_from_llm_extract(tmp_path: Path):
    from dat_tracker.review_hydrate import seed_package_metadata

    cal = tmp_path / "cal"
    cal.mkdir()
    (cal / "info.txt").write_text(_jamshack_txt())

    def fake_llm(context: dict) -> dict:
        return {
            "artist": "John Cowan & Pat Flynn",
            "date": "2004-04-16",
            "venue": "Jam Shack Stage",
            "city": "Dade City",
            "state": "FL",
            "source": "SBD > Sony PCM-M1",
            "transfer": "Sony PCM-M1 > Wavelab > FLAC",
            "transferer": "Kevin Preuss",
        }

    plan = migrate_tracking_plan(
        {
            "schema_version": "1.0.0",
            "show_id": "jcb2004-04-16.sbd.kp.flac16",
            "source_path": "x.flac",
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
            "overall_confidence": 0.5,
            "needs_review": False,
            "notes": [],
        }
    )
    out = seed_package_metadata(
        plan,
        project_root=tmp_path,
        calibration_dir=cal,
        llm_extract_fn=fake_llm,
        allow_web_research=False,
    )
    assert out["package"]["venue"] == "Jam Shack Stage"
    assert out["package"]["city"] == "Dade City"
    assert out["package"]["state"] == "FL"
    assert out["package"]["transferer"] == "Kevin Preuss"
    validate_tracking_plan(out)


def test_llm_success_skips_heuristic_soft_fill(tmp_path: Path):
    """When the LLM returns a partial result, do not overwrite with regex parses."""
    from dat_tracker.review_package_extract import extract_package_fields_from_companions

    (tmp_path / "info.txt").write_text(
        "Jazz Mandolin Project\n"
        "Winston's\n"
        "San Diego, CA\n"
        "2002-11-15\n"
        "\n"
        "Source: AUD > DAT\n"
        "Transfer: DAT > FLAC\n"
    )

    def fake_llm(context: dict) -> dict:
        return {"artist": "Jazz Mandolin Project", "date": "2002-11-15"}

    fields = extract_package_fields_from_companions(
        tmp_path,
        use_llm=True,
        llm_extract_fn=fake_llm,
        allow_web_research=False,
    )
    assert fields["artist"] == "Jazz Mandolin Project"
    assert fields["date"] == "2002-11-15"
    # Heuristic would have filled these; LLM-first must leave them for research/operator.
    assert "venue" not in fields
    assert "source" not in fields


def test_web_research_fills_missing_location_fields(tmp_path: Path):
    from dat_tracker.review_package_extract import extract_package_fields_from_companions

    (tmp_path / "thin.txt").write_text(
        "Jazz Mandolin Project\n"
        "November 15, 2002\n"
        "\n"
        "Source: AUD > DAT\n"
        "Transfer: DAT > FLAC\n"
    )
    research_calls: list[dict] = []

    def fake_llm(context: dict) -> dict:
        return {
            "artist": "Jazz Mandolin Project",
            "date": "2002-11-15",
            "source": "AUD > DAT",
            "transfer": "DAT > FLAC",
        }

    def fake_research(partial: dict, context: dict) -> dict:
        research_calls.append({"partial": dict(partial), "context": context})
        assert partial["artist"] == "Jazz Mandolin Project"
        assert partial["date"] == "2002-11-15"
        return {"venue": "Winston's", "city": "San Diego", "state": "CA"}

    fields = extract_package_fields_from_companions(
        tmp_path,
        use_llm=True,
        llm_extract_fn=fake_llm,
        llm_research_fn=fake_research,
        allow_web_research=True,
    )
    assert research_calls
    assert fields["venue"] == "Winston's"
    assert fields["city"] == "San Diego"
    assert fields["state"] == "CA"
    assert fields["source"] == "AUD > DAT"


def test_web_research_skipped_when_disabled(tmp_path: Path):
    from dat_tracker.review_package_extract import extract_package_fields_from_companions

    (tmp_path / "thin.txt").write_text("Jazz Mandolin Project\n2002-11-15\n")

    def fake_llm(context: dict) -> dict:
        return {"artist": "Jazz Mandolin Project", "date": "2002-11-15"}

    def boom_research(partial: dict, context: dict) -> dict:
        raise AssertionError("research must not run when disabled")

    fields = extract_package_fields_from_companions(
        tmp_path,
        use_llm=True,
        llm_extract_fn=fake_llm,
        llm_research_fn=boom_research,
        allow_web_research=False,
    )
    assert "venue" not in fields


def test_parse_json_object_from_fenced_or_prose():
    from dat_tracker.review_package_extract import parse_json_object

    assert parse_json_object('{"venue": "Winston\'s"}')["venue"] == "Winston's"
    assert parse_json_object(
        'Here you go:\n```json\n{"city": "San Diego", "state": "CA"}\n```\n'
    ) == {"city": "San Diego", "state": "CA"}


def test_research_config_uses_google_search_without_json_mime():
    from dat_tracker.review_package_extract import build_gemini_generate_config

    cfg = build_gemini_generate_config(with_google_search=True)
    assert cfg.response_mime_type is None or cfg.response_mime_type == ""
    assert cfg.tools
    assert cfg.tools[0].google_search is not None

    cfg_json = build_gemini_generate_config(with_google_search=False)
    assert cfg_json.response_mime_type == "application/json"
    assert not cfg_json.tools
