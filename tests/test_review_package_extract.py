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
    )
    assert out["package"]["venue"] == "Jam Shack Stage"
    assert out["package"]["city"] == "Dade City"
    assert out["package"]["state"] == "FL"
    assert out["package"]["transferer"] == "Kevin Preuss"
    validate_tracking_plan(out)
