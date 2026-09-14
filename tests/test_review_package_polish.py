"""Tests for package metadata spelling / name polish."""

from __future__ import annotations

from dat_tracker.review_package_polish import (
    apply_known_spelling_fixes,
    polish_package_metadata,
)
from dat_tracker.review_plan import migrate_tracking_plan
from dat_tracker.tracking_plan import validate_tracking_plan


def _plan(**pkg):
    base = migrate_tracking_plan(
        {
            "schema_version": "1.0.0",
            "show_id": "sbb2001-04-27.flac16",
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
                    "confidence": 0.8,
                    "evidence": [],
                }
            ],
            "overall_confidence": 0.8,
            "needs_review": False,
            "notes": [],
        }
    )
    base["package"].update(pkg)
    return base


def test_apply_known_spelling_fixes_douglass():
    assert (
        apply_known_spelling_fixes("Sam Bush & Jerry Douglass")
        == "Sam Bush & Jerry Douglas"
    )


def test_polish_package_fixes_artist_from_published_typo():
    plan = _plan(
        artist="Sam Bush & Jerry Douglass",
        notes="Wilkes Community college",
    )
    out = polish_package_metadata(plan, use_llm=False)
    validate_tracking_plan(out)
    assert out["package"]["artist"] == "Sam Bush & Jerry Douglas"
    assert out["package"]["notes"] == "Wilkes Community College"
    assert any("Polished package metadata" in str(n) for n in out["notes"])


def test_polish_package_is_idempotent():
    plan = polish_package_metadata(
        _plan(artist="Sam Bush & Jerry Douglass"), use_llm=False
    )
    again = polish_package_metadata(plan, use_llm=False)
    assert again["package"]["artist"] == "Sam Bush & Jerry Douglas"
    assert sum(
        1 for n in again["notes"] if "Polished package metadata" in str(n)
    ) == 1


def test_polish_package_llm_can_correct_artist():
    plan = _plan(artist="Sam Bush & Jerry Douglass")

    def fake_llm(fields: dict) -> dict:
        assert "Douglass" in (fields.get("artist") or "")
        return {**fields, "artist": "Sam Bush & Jerry Douglas"}

    # Skip known fixes so LLM path is exercised.
    out = polish_package_metadata(
        plan, use_llm=True, known_fixes=False, llm_polish_fn=fake_llm
    )
    assert out["package"]["artist"] == "Sam Bush & Jerry Douglas"


def test_polish_package_llm_skipped_when_already_polished():
    plan = polish_package_metadata(
        _plan(artist="Sam Bush & Jerry Douglass"), use_llm=False
    )
    calls = {"n": 0}

    def boom(fields: dict) -> dict:
        calls["n"] += 1
        raise AssertionError("LLM should not run after polish note is present")

    polish_package_metadata(plan, use_llm=True, llm_polish_fn=boom)
    assert calls["n"] == 0
