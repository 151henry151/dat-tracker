"""Tests for Dropbox dump path / zip listing → candidate catalog rows."""

from dat_tracker.catalog_raw import (
    infer_collection_from_path,
    parse_zip_listing_line,
    shows_from_zip_paths,
)


def test_infer_collection_dave_and_brian():
    assert (
        infer_collection_from_path("Live Bluegrass/Dave W Flacs/foo.flac")
        == "Dave Ward Collection"
    )
    assert (
        infer_collection_from_path("Brian H Flacs Wave 2/bar.flac")
        == "Brian H Collection"
    )


def test_parse_zip_listing_line_extracts_path():
    line = " 1234567890  2026-09-07 12:00   Dave W Flacs/John Cowan 2002-08-02.flac"
    assert (
        parse_zip_listing_line(line)
        == "Dave W Flacs/John Cowan 2002-08-02.flac"
    )


def test_shows_from_zip_paths_builds_todo_rows():
    paths = [
        "Dave W Flacs/John Cowan 2002-08-02.flac",
        "Brian H Flacs/del2005-05-29.flac",
        "Read Me_090726.txt",
        "Dave W Flacs/some-photo.jpg",
    ]
    shows = shows_from_zip_paths(paths)
    assert len(shows) == 2
    by_path = {s["raw_path"]: s for s in shows}
    assert by_path["Dave W Flacs/John Cowan 2002-08-02.flac"]["status"] == "todo"
    assert (
        by_path["Dave W Flacs/John Cowan 2002-08-02.flac"]["collection"]
        == "Dave Ward Collection"
    )
    assert by_path["Brian H Flacs/del2005-05-29.flac"]["date"] == "2005-05-29"
    assert by_path["Brian H Flacs/del2005-05-29.flac"]["id"] == "del2005-05-29"
