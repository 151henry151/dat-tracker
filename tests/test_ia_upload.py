"""Tests for Archive.org metadata + upload helpers (mocked, no network)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from dat_tracker.review_plan import migrate_tracking_plan


def _plan() -> dict:
    return migrate_tracking_plan(
        {
            "schema_version": "1.0.0",
            "show_id": "jmp2002-11-15",
            "source_path": "x.flac",
            "duration_sec": 10.0,
            "cuts_sec": [0.0, 10.0],
            "tracks": [
                {
                    "index": 1,
                    "start_sec": 0.0,
                    "end_sec": 10.0,
                    "track_type": "song",
                    "title": "Mariachi Song",
                    "segue_into_next": False,
                    "confidence": 0.9,
                    "evidence": [],
                }
            ],
            "overall_confidence": 0.9,
            "needs_review": False,
            "notes": [],
            "package": {
                "artist": "Jazz Mandolin Project",
                "date": "2002-11-15",
                "venue": "Winston's",
                "city": "San Diego",
                "state": "CA",
                "source": "AUD > DAT",
                "transfer": "DAT > FLAC",
                "transferer": "Cate Crowe",
                "tracker": "Henry",
                "set_label": "One Set",
                "collection_subjects": ["Brian H Collection"],
                "notes": None,
            },
            "review": {
                "status": "approved",
                "approved_at": "2026-01-01T00:00:00+00:00",
                "approved_by": "Henry",
                "method": "accept_all",
            },
        }
    )


def test_build_ia_metadata_includes_credits_and_subjects():
    from dat_tracker.ia_upload import build_ia_metadata

    meta = build_ia_metadata(
        _plan(), collection="taperssection", identifier="jmp2002-11-15"
    )
    assert meta["collection"] == ["taperssection"]
    assert meta["mediatype"] == "audio"
    assert meta["creator"] == "Jazz Mandolin Project"
    assert meta["date"] == "2002-11-15"
    assert "Winston" in meta["venue"]
    assert meta["coverage"] == "San Diego, CA"
    assert "Brian H Collection" in meta["subject"]
    assert "Cate Crowe" in meta.get("lineage", "") or "Cate" in str(meta)
    assert meta["identifier"] == "jmp2002-11-15"


def test_catalog_marks_already_uploaded(tmp_path: Path):
    import json

    from dat_tracker.ia_upload import catalog_blocks_upload

    cat = tmp_path / "catalog"
    cat.mkdir()
    (cat / "shows.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0.0",
                "shows": [
                    {
                        "id": "jmp2002-11-15",
                        "status": "already_uploaded",
                        "artist": "Jazz Mandolin Project",
                    }
                ],
            }
        )
    )
    assert catalog_blocks_upload("jmp2002-11-15", project_root=tmp_path) is True
    assert catalog_blocks_upload("other-show", project_root=tmp_path) is False


def test_upload_package_calls_session_upload(tmp_path: Path, monkeypatch):
    from dat_tracker import ia_upload

    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "a.flac").write_bytes(b"fLaC")
    (pkg / "show.txt").write_text("x")

    session = MagicMock()
    session.upload.return_value = [MagicMock()]
    monkeypatch.setattr(
        ia_upload, "_get_ia_session", lambda: session
    )
    monkeypatch.setattr(ia_upload, "ia_configured", lambda: True)
    monkeypatch.setattr(
        ia_upload, "identifier_exists", lambda _i: False
    )

    result = ia_upload.upload_package(
        pkg,
        identifier="jmp2002-11-15",
        metadata=ia_upload.build_ia_metadata(
            _plan(), collection="taperssection", identifier="jmp2002-11-15"
        ),
        project_root=tmp_path,
    )
    assert result.ok
    assert result.identifier == "jmp2002-11-15"
    assert "archive.org/details/jmp2002-11-15" in (result.item_url or "")
    session.upload.assert_called_once()
    args, kwargs = session.upload.call_args
    assert args[0] == "jmp2002-11-15"
