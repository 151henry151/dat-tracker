"""Tests for persistent operator review defaults (transferer, transfer, set_label)."""

from __future__ import annotations

import json
from pathlib import Path

from dat_tracker.review_defaults import (
    OPERATOR_DEFAULT_KEYS,
    defaults_are_configured,
    load_operator_defaults,
    save_operator_defaults,
    user_defaults_path,
)
from dat_tracker.review_hydrate import seed_package_metadata
from dat_tracker.review_plan import migrate_tracking_plan


def _bare_plan():
    return migrate_tracking_plan(
        {
            "schema_version": "1.0.0",
            "show_id": "demo2001-01-01",
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


def test_save_and_load_operator_defaults(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("DAT_TRACKER_DEFAULTS", str(tmp_path / "defaults.json"))
    path = save_operator_defaults(
        {
            "transferer": "Cate Crowe",
            "transfer": "DAT > PCM-2600 > FLAC",
            "tracker": "Jon King",
            "set_label": "One Set",
        },
        project_root=tmp_path,
    )
    assert path.is_file()
    loaded = load_operator_defaults(project_root=tmp_path)
    assert loaded["transferer"] == "Cate Crowe"
    assert loaded["transfer"] == "DAT > PCM-2600 > FLAC"
    assert loaded["tracker"] == "Jon King"
    assert loaded["set_label"] == "One Set"
    assert defaults_are_configured(project_root=tmp_path)


def test_project_catalog_defaults_preferred(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("DAT_TRACKER_DEFAULTS", raising=False)
    catalog = tmp_path / "catalog"
    catalog.mkdir()
    (catalog / "operator_defaults.json").write_text(
        json.dumps({"transferer": "From Project", "set_label": "Set 1"}) + "\n"
    )
    loaded = load_operator_defaults(project_root=tmp_path)
    assert loaded["transferer"] == "From Project"
    assert loaded["set_label"] == "Set 1"


def test_seed_applies_operator_defaults_and_set_label_fallback(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("DAT_TRACKER_DEFAULTS", str(tmp_path / "defaults.json"))
    save_operator_defaults(
        {
            "transferer": "Cate Crowe",
            "transfer": "DAT > FLAC",
            "tracker": "Operator",
        },
        project_root=tmp_path,
    )
    plan = seed_package_metadata(_bare_plan(), project_root=tmp_path)
    assert plan["package"]["transferer"] == "Cate Crowe"
    assert plan["package"]["transfer"] == "DAT > FLAC"
    assert plan["package"]["tracker"] == "Operator"
    # Soft default when unset in operator file.
    assert plan["package"]["set_label"] == "One Set"


def test_seed_does_not_overwrite_existing_package_fields(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("DAT_TRACKER_DEFAULTS", str(tmp_path / "defaults.json"))
    save_operator_defaults({"transferer": "Default Person"}, project_root=tmp_path)
    plan = _bare_plan()
    plan["package"]["transferer"] = "Already Set"
    out = seed_package_metadata(plan, project_root=tmp_path)
    assert out["package"]["transferer"] == "Already Set"


def test_operator_default_keys_cover_credit_fields():
    assert "transfer" in OPERATOR_DEFAULT_KEYS
    assert "transferer" in OPERATOR_DEFAULT_KEYS
    assert "tracker" in OPERATOR_DEFAULT_KEYS
    assert "set_label" in OPERATOR_DEFAULT_KEYS


def test_user_defaults_path_under_config_home(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    monkeypatch.delenv("DAT_TRACKER_DEFAULTS", raising=False)
    path = user_defaults_path()
    assert path == tmp_path / "cfg" / "dat-tracker" / "review_defaults.json"
