"""Tests for merging raw dump candidates with IA already-uploaded rows."""

from dat_tracker.catalog_merge import merge_catalog


def test_merge_marks_matching_raw_show_already_uploaded():
    raw = [
        {
            "id": "jcb2002-08-02",
            "raw_path": "Dave W Flacs/John Cowan 2002-08-02.flac",
            "artist": "John Cowan",
            "date": "2002-08-02",
            "venue": None,
            "city": None,
            "state": None,
            "collection": "Dave Ward Collection",
            "status": "todo",
            "ia_identifier": None,
            "ia_collection": None,
            "source": None,
            "notes": None,
        },
        {
            "id": "unknown2001-01-01",
            "raw_path": "Dave W Flacs/Mystery Band 2001-01-01.flac",
            "artist": "Mystery Band",
            "date": "2001-01-01",
            "venue": None,
            "city": None,
            "state": None,
            "collection": "Dave Ward Collection",
            "status": "todo",
            "ia_identifier": None,
            "ia_collection": None,
            "source": None,
            "notes": None,
        },
    ]
    ia = [
        {
            "id": "jcb2002-08-02",
            "raw_path": "",
            "artist": "John Cowan",
            "date": "2002-08-02",
            "venue": "Riverbend Music Center",
            "city": "Cincinnati",
            "state": "OH",
            "collection": "Dave Ward Collection",
            "status": "already_uploaded",
            "ia_identifier": "jcb2002-08-02",
            "ia_collection": "JohnCowan",
            "source": None,
            "notes": None,
        }
    ]
    merged = merge_catalog(raw_shows=raw, ia_shows=ia)
    by_id = {s["id"]: s for s in merged}
    assert by_id["jcb2002-08-02"]["status"] == "already_uploaded"
    assert by_id["jcb2002-08-02"]["raw_path"].endswith(".flac")
    assert by_id["jcb2002-08-02"]["venue"] == "Riverbend Music Center"
    assert by_id["unknown2001-01-01"]["status"] == "todo"
    assert len(merged) == 2
