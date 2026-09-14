"""Tests for J-card image discovery wiring into package extract."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from dat_tracker.jcard_extract import (
    extract_package_fields_from_jcards,
    jcard_extract_for_audio,
)


def test_extract_jcards_returns_empty_without_images(tmp_path: Path):
    assert extract_package_fields_from_jcards([]) == {}
    flac = tmp_path / "x.flac"
    flac.write_bytes(b"f")
    assert jcard_extract_for_audio(flac, use_llm=False) == {}


def test_extract_jcards_uses_llm_fn(tmp_path: Path):
    img = tmp_path / "show.jpg"
    img.write_bytes(b"JFIF")
    events: list[Path] = []

    def fake_llm(images: list[Path], **_kwargs):
        events.extend(images)
        return {
            "date": "2003-06-13",
            "artist": "McNasty > Bluegrass Brethren",
            "notes": "DAT 1",
        }

    out = extract_package_fields_from_jcards(
        [img], use_llm=True, llm_vision_fn=fake_llm
    )
    assert events == [img]
    assert out["date"] == "2003-06-13"
    assert "McNasty" in out["artist"]


def test_jcard_extract_for_audio_finds_sibling(tmp_path: Path):
    stem = "06132003_HF_01-x"
    flac = tmp_path / f"{stem}.flac"
    jpg = tmp_path / f"{stem}.jpg"
    flac.write_bytes(b"f")
    jpg.write_bytes(b"JFIF")

    with patch(
        "dat_tracker.jcard_extract.extract_package_fields_from_jcards",
        return_value={"date": "2003-06-13"},
    ) as mock_ex:
        out = jcard_extract_for_audio(flac, use_llm=True)
    assert out["date"] == "2003-06-13"
    assert mock_ex.call_args[0][0][0].resolve() == jpg.resolve()
