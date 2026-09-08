"""Tests for synthetic continuous FLAC re-split ground truth."""

from pathlib import Path

from dat_tracker.boundaries import cuts_from_durations
from dat_tracker.resplit import (
    build_concat_list_file,
    known_cuts_from_track_dir,
    synthetic_raw_path_for,
)


def test_known_cuts_from_track_dir_uses_probe_order(tmp_path, monkeypatch):
    t01 = tmp_path / "show_t01.flac"
    t02 = tmp_path / "show_t02.flac"
    synth = tmp_path / "synthetic_continuous.flac"
    t01.write_bytes(b"")
    t02.write_bytes(b"")
    synth.write_bytes(b"")

    def fake_probe(path: Path) -> float:
        return {t01: 10.0, t02: 5.0, synth: 999.0}[path]

    monkeypatch.setattr("dat_tracker.resplit.probe_duration_seconds", fake_probe)
    cuts, tracks = known_cuts_from_track_dir(tmp_path)
    assert [p.name for p in tracks] == ["show_t01.flac", "show_t02.flac"]
    assert cuts == cuts_from_durations([10.0, 5.0])


def test_build_concat_list_file_writes_ffmpeg_concat_lines(tmp_path):
    a = tmp_path / "a.flac"
    b = tmp_path / "b.flac"
    a.write_bytes(b"")
    b.write_bytes(b"")
    out = tmp_path / "list.txt"
    build_concat_list_file([a, b], out)
    text = out.read_text()
    assert f"file '{a.resolve()}'" in text
    assert f"file '{b.resolve()}'" in text


def test_build_concat_list_file_escapes_apostrophes_in_paths(tmp_path):
    tricky = tmp_path / "Sailin' Away.flac"
    tricky.write_bytes(b"")
    out = tmp_path / "list.txt"
    build_concat_list_file([tricky], out)
    # ffmpeg concat quoting: close quote, escaped quote, reopen
    assert r"'\''" in out.read_text()


def test_synthetic_raw_path_for_nests_under_calibration():
    path = synthetic_raw_path_for(Path("/proj/data/calibration"), "del2001-04-27.flac16")
    assert path == Path(
        "/proj/data/calibration/del2001-04-27.flac16/synthetic_continuous.flac"
    )
