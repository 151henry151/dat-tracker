"""Tests for catalog JSON/CSV serialization."""

from dat_tracker.catalog_io import catalog_to_csv, catalog_document, shows_from_catalog


def test_catalog_document_wraps_shows():
    shows = [{"id": "x", "status": "todo"}]
    doc = catalog_document(shows)
    assert doc["schema_version"] == "1.0.0"
    assert doc["shows"] == shows


def test_catalog_to_csv_includes_header_and_row():
    shows = [
        {
            "id": "jcb2002-08-02",
            "raw_path": "Dave W Flacs/a.flac",
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
    csv_text = catalog_to_csv(shows)
    lines = csv_text.strip().splitlines()
    assert lines[0].startswith("id,raw_path,artist,date,")
    assert "jcb2002-08-02" in lines[1]
    assert "Dave Ward Collection" in lines[1]


def test_shows_from_catalog_reads_document():
    doc = {"schema_version": "1.0.0", "shows": [{"id": "a"}]}
    assert shows_from_catalog(doc) == [{"id": "a"}]
