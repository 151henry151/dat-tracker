"""Tests for dump path / filename package-metadata heuristics."""

from __future__ import annotations

from pathlib import Path

from dat_tracker.dump_metadata import (
    expand_artist_token,
    find_sibling_jcard_images,
    infer_dump_package_fields,
    parse_artists_from_stem,
    parse_date_from_stem,
    parse_venue_from_folder,
)


def test_parse_date_mmddyyyy():
    assert parse_date_from_stem("06132003_HF_01-McNasty") == "2003-06-13"
    assert parse_date_from_stem("06142003_HF_02-Sturgis") == "2003-06-14"


def test_parse_date_yymmdd_dave_style():
    assert parse_date_from_stem("010407_JCB_1") == "2001-04-07"
    assert parse_date_from_stem("950703_LOS_plus_Box_Set") == "1995-07-03"


def test_parse_date_yyyymmdd():
    assert parse_date_from_stem("20030615_HFMF_Del_McCoury") == "2003-06-15"


def test_parse_date_iso_embedded():
    assert parse_date_from_stem("del2005-05-29") == "2005-05-29"
    assert parse_date_from_stem("ymsb2003-04-18.Matrix") == "2003-04-18"


def test_parse_artists_from_arrow_stem():
    artists = parse_artists_from_stem(
        "06132003_HF_01-McNasty→Shiflett→BGBrethren"
    )
    assert artists == ["McNasty", "Shiflett", "Bluegrass Brethren"]


def test_expand_known_abbreviations():
    assert expand_artist_token("BGBrethren") == "Bluegrass Brethren"
    assert expand_artist_token("JCB") == "John Cowan Band"
    assert expand_artist_token("McNasty") == "McNasty"


def test_parse_venue_from_festival_folder():
    assert (
        parse_venue_from_folder("Huck Finn Festival - April 2003")
        == "Huck Finn Festival"
    )
    assert (
        parse_venue_from_folder("Old Settlers Music Festival - June 2003")
        == "Old Settlers Music Festival"
    )


def test_infer_dump_fields_huck_finn_path(tmp_path: Path):
    flac = (
        tmp_path
        / "Brian H Flacs Wave 2"
        / "Huck Finn Festival - April 2003"
        / "06132003_HF_01-McNasty→Shiflett→BGBrethren.flac"
    )
    flac.parent.mkdir(parents=True)
    flac.write_bytes(b"f")
    fields = infer_dump_package_fields(flac, dump_root=tmp_path)
    assert fields["date"] == "2003-06-13"
    assert fields["venue"] == "Huck Finn Festival"
    assert "McNasty" in fields["artist"]
    assert "Bluegrass Brethren" in fields["artist"]
    assert fields["collection_subjects"] == ["Brian H Collection"]
    assert fields["transferer"] == "Cate Crowe"
    assert "DAT" in (fields.get("transfer") or "")
    assert fields.get("source")  # Brian lineage note


def test_infer_dump_fields_dave_w(tmp_path: Path):
    flac = tmp_path / "Dave W Flacs" / "020802_JCB_RR.flac"
    flac.parent.mkdir(parents=True)
    flac.write_bytes(b"f")
    fields = infer_dump_package_fields(flac, dump_root=tmp_path)
    assert fields["date"] == "2002-08-02"
    assert fields["collection_subjects"] == ["Dave Ward Collection"]
    assert "SBD" in (fields.get("source") or "").upper() or "soundboard" in (
        fields.get("source") or ""
    ).lower()


def test_find_sibling_jcard_images(tmp_path: Path):
    stem = "06132003_HF_01-McNasty→Shiflett→BGBrethren"
    flac = tmp_path / f"{stem}.flac"
    jpg = tmp_path / f"{stem}.jpg"
    other = tmp_path / "unrelated.jpg"
    flac.write_bytes(b"f")
    jpg.write_bytes(b"JFIF")
    other.write_bytes(b"x")
    found = find_sibling_jcard_images(flac)
    assert jpg.resolve() in [p.resolve() for p in found]
    assert other.resolve() not in [p.resolve() for p in found]
