"""Tests for Archive.org search docs → catalog show rows."""

from dat_tracker.catalog_ia import ia_doc_to_show, shows_from_ia_response


def test_ia_doc_to_show_maps_dave_ward_fields():
    doc = {
        "identifier": "jcb2002-08-02",
        "title": "John Cowan Live at Riverbend Music Center on 2002-08-02",
        "creator": "John Cowan",
        "date": "2002-08-02T00:00:00Z",
        "venue": "Riverbend Music Center",
        "coverage": "Cincinnati, OH",
        "collection": ["JohnCowan", "etree"],
        "subject": ["Live concert", "Dave Ward Collection"],
    }
    show = ia_doc_to_show(doc)
    assert show["id"] == "jcb2002-08-02"
    assert show["artist"] == "John Cowan"
    assert show["date"] == "2002-08-02"
    assert show["venue"] == "Riverbend Music Center"
    assert show["city"] == "Cincinnati"
    assert show["state"] == "OH"
    assert show["collection"] == "Dave Ward Collection"
    assert show["status"] == "already_uploaded"
    assert show["ia_identifier"] == "jcb2002-08-02"
    assert show["ia_collection"] == "JohnCowan"
    assert show["raw_path"] == ""


def test_ia_doc_prefers_taperssection_when_no_band_collection():
    doc = {
        "identifier": "hotrize1996-06-09",
        "creator": "Hot Rize",
        "date": "1996-06-09T00:00:00Z",
        "collection": ["taperssection", "audio_music"],
        "subject": ["Dave Ward Collection"],
    }
    show = ia_doc_to_show(doc)
    assert show["ia_collection"] == "taperssection"
    assert show["collection"] == "Dave Ward Collection"


def test_shows_from_ia_response_collects_docs():
    payload = {
        "response": {
            "docs": [
                {
                    "identifier": "del2005-05-29",
                    "creator": "Del McCoury Band",
                    "date": "2005-05-29T00:00:00Z",
                    "collection": ["DelMcCouryBand", "etree"],
                    "subject": ["Brian H Collection"],
                }
            ]
        }
    }
    shows = shows_from_ia_response(payload)
    assert len(shows) == 1
    assert shows[0]["collection"] == "Brian H Collection"
    assert shows[0]["status"] == "already_uploaded"


def test_ia_doc_parses_comma_joined_subject_string():
    doc = {
        "identifier": "jmp2002-11-15",
        "creator": "Jazz Mandolin Project",
        "date": "2002-11-15T00:00:00Z",
        "collection": ["JazzMandolinProject", "etree"],
        "subject": "Live concert, Brian H Collection",
    }
    show = ia_doc_to_show(doc)
    assert show["collection"] == "Brian H Collection"
