"""Tests for Dropbox dump path / zip listing → candidate catalog rows."""

from dat_tracker.catalog_raw import (
    infer_collection_from_path,
    parse_zip_listing_line,
    path_to_show,
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


def test_path_to_show_parses_yymmdd_abbrev_dump_names():
    show = path_to_show("Dave W Flacs/020802_JCB_RR.flac")
    assert show is not None
    assert show["date"] == "2002-08-02"
    assert show["id"] == "jcb2002-08-02"
    assert show["artist"] == "John Cowan"
    assert show["collection"] == "Dave Ward Collection"
    assert show["raw_path"] == "Dave W Flacs/020802_JCB_RR.flac"


def test_path_to_show_parses_yyyymmdd_festival_names():
    show = path_to_show(
        "Brian H Flacs Wave 3/2005 Strawberry Spring Music Festival/"
        "20050529_STRAW_14_FM_Del_McCoury_Band.flac"
    )
    assert show is not None
    assert show["date"] == "2005-05-29"
    assert show["id"] == "del2005-05-29"
    assert show["artist"] == "Del McCoury Band"
    assert show["collection"] == "Brian H Collection"


def test_shows_from_zip_paths_coalesces_multipart_same_show():
    paths = [
        "Dave W Flacs/000401_JCB_1.flac",
        "Dave W Flacs/000401_JCB_2.flac",
        "Read Me_090726.txt",
        "Dave W Flacs/some-photo.jpg",
    ]
    shows = shows_from_zip_paths(paths)
    assert len(shows) == 1
    show = shows[0]
    assert show["id"] == "jcb2000-04-01"
    assert show["date"] == "2000-04-01"
    assert "000401_JCB_1.flac" in show["raw_path"]
    assert "000401_JCB_2.flac" in show["raw_path"]


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
