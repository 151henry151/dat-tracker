"""Tests for persistent operator review defaults (tracker name)."""

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
    path = save_operator_defaults({"tracker": "Jon King"}, project_root=tmp_path)
    assert path.is_file()
    loaded = load_operator_defaults(project_root=tmp_path)
    assert loaded == {"tracker": "Jon King"}
    assert defaults_are_configured(project_root=tmp_path)


def test_save_strips_legacy_transfer_keys(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("DAT_TRACKER_DEFAULTS", str(tmp_path / "defaults.json"))
    path = tmp_path / "defaults.json"
    path.write_text(
        json.dumps(
            {
                "tracker": "Old",
                "transfer": "DAT > FLAC",
                "transferer": "Cate",
                "set_label": "One Set",
            }
        )
        + "\n"
    )
    save_operator_defaults({"tracker": "New Name"}, project_root=tmp_path)
    raw = json.loads(path.read_text())
    assert raw == {"tracker": "New Name"}


def test_project_catalog_defaults_preferred(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("DAT_TRACKER_DEFAULTS", raising=False)
    catalog = tmp_path / "catalog"
    catalog.mkdir()
    (catalog / "operator_defaults.json").write_text(
        json.dumps({"tracker": "From Project"}) + "\n"
    )
    loaded = load_operator_defaults(project_root=tmp_path)
    assert loaded["tracker"] == "From Project"


def test_seed_applies_tracker_default_and_set_label_fallback(
    tmp_path: Path, monkeypatch
):
    monkeypatch.setenv("DAT_TRACKER_DEFAULTS", str(tmp_path / "defaults.json"))
    save_operator_defaults({"tracker": "Operator"}, project_root=tmp_path)
    plan = seed_package_metadata(_bare_plan(), project_root=tmp_path)
    assert plan["package"]["tracker"] == "Operator"
    assert plan["package"]["set_label"] == "One Set"
    assert plan["package"]["transfer"] is None
    assert plan["package"]["transferer"] is None


def test_seed_replaces_placeholder_tracker_with_operator_default(
    tmp_path: Path, monkeypatch
):
    monkeypatch.setenv("DAT_TRACKER_DEFAULTS", str(tmp_path / "defaults.json"))
    save_operator_defaults({"tracker": "Henry Romp"}, project_root=tmp_path)
    plan = _bare_plan()
    plan["package"]["tracker"] = "dat-tracker"
    out = seed_package_metadata(plan, project_root=tmp_path)
    assert out["package"]["tracker"] == "Henry Romp"


def test_operator_default_keys_are_tracker_only():
    assert OPERATOR_DEFAULT_KEYS == ("tracker",)


def test_user_defaults_path_under_config_home(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    monkeypatch.delenv("DAT_TRACKER_DEFAULTS", raising=False)
    path = user_defaults_path()
    assert path == tmp_path / "cfg" / "dat-tracker" / "review_defaults.json"
