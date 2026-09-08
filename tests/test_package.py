"""Tests for packaging show.txt and fingerprint.ffp.txt from a tracking plan."""

from pathlib import Path

from dat_tracker.package import (
    flac_streaminfo_md5,
    format_fingerprint_ffp,
    package_show_from_plan,
    setlist_entries_from_plan,
)


def test_flac_streaminfo_md5_reads_header(tmp_path: Path):
    import subprocess

    src = tmp_path / "tone.flac"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=880:sample_rate=44100:duration=0.5",
            "-c:a",
            "flac",
            str(src),
        ],
        check=True,
        capture_output=True,
    )
    md5 = flac_streaminfo_md5(src)
    assert len(md5) == 32
    assert all(c in "0123456789abcdef" for c in md5)


def test_format_fingerprint_ffp_matches_etree_shape():
    text = format_fingerprint_ffp(
        [
            ("show_t01.flac", "aabbccddeeff00112233445566778899"),
            ("show_t02.flac", "00112233445566778899aabbccddeeff"),
        ]
    )
    assert "show_t01.flac:aabbccddeeff00112233445566778899" in text
    assert "show_t02.flac:00112233445566778899aabbccddeeff" in text


def test_setlist_entries_from_plan_uses_titles_and_types():
    plan = {
        "tracks": [
            {
                "index": 1,
                "title": None,
                "track_type": "song",
                "segue_into_next": True,
            },
            {
                "index": 2,
                "title": "Beauty of My Dreams",
                "track_type": "song",
                "segue_into_next": False,
            },
            {
                "index": 3,
                "title": "Band Introductions / Outro",
                "track_type": "banter",
                "segue_into_next": False,
            },
        ]
    }
    entries = setlist_entries_from_plan(plan)
    assert entries[0]["num"] == 1
    assert entries[0]["title"].endswith(">")
    assert entries[1]["title"] == "Beauty of My Dreams"
    assert "banter" in entries[2]["title"].lower() or entries[2]["title"].startswith(
        "Band"
    )


def test_package_show_from_plan_writes_txt_and_ffp(tmp_path: Path):
    import subprocess

    t1 = tmp_path / "demo2001-01-01_t01.flac"
    t2 = tmp_path / "demo2001-01-01_t02.flac"
    for path, freq in ((t1, 440), (t2, 550)):
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-f",
                "lavfi",
                "-i",
                f"sine=frequency={freq}:sample_rate=44100:duration=0.4",
                "-c:a",
                "flac",
                str(path),
            ],
            check=True,
            capture_output=True,
        )
    plan = {
        "show_id": "demo2001-01-01",
        "tracks": [
            {
                "index": 1,
                "title": "Opener",
                "track_type": "song",
                "segue_into_next": False,
            },
            {
                "index": 2,
                "title": None,
                "track_type": "banter",
                "segue_into_next": False,
            },
        ],
    }
    result = package_show_from_plan(
        plan,
        track_paths=[t1, t2],
        out_dir=tmp_path,
        artist="Demo Band",
        date="2001-01-01",
        tracker="Henry",
    )
    txt = (tmp_path / "demo2001-01-01.txt").read_text()
    ffp = (tmp_path / "fingerprint.ffp.txt").read_text()
    assert "Demo Band" in txt
    assert "1. Opener" in txt
    assert "demo2001-01-01_t01.flac:" in ffp
    assert result["txt"].name == "demo2001-01-01.txt"
    assert result["ffp"].name == "fingerprint.ffp.txt"
