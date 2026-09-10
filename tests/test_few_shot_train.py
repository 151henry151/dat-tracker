"""Tests for train-only few-shot exemplar loading."""

from pathlib import Path

from dat_tracker.gemini_tracker import load_train_few_shot_examples


def test_load_train_few_shot_excludes_self_and_missing(tmp_path: Path):
    catalog = tmp_path / "catalog"
    catalog.mkdir()
    cal = tmp_path / "data" / "calibration" / "sbb2001-04-27.flac16"
    cal.mkdir(parents=True)
    audio = cal / "synthetic_continuous.flac"
    audio.write_bytes(b"flac")
    (catalog / "few_shot_train.json").write_text(
        """
{
  "examples": [
    {
      "show_id": "sbb2001-04-27.flac16",
      "cut_sec": 100.0,
      "label": "ok",
      "audio": "data/calibration/sbb2001-04-27.flac16/synthetic_continuous.flac"
    },
    {
      "show_id": "missing-show",
      "cut_sec": 50.0,
      "label": "gone",
      "audio": "data/calibration/missing/synthetic_continuous.flac"
    }
  ]
}
"""
    )
    # Exclude self → empty because only valid audio is self.
    assert load_train_few_shot_examples(
        project_root=tmp_path, exclude_show_id="sbb2001-04-27.flac16"
    ) == []
    got = load_train_few_shot_examples(
        project_root=tmp_path, exclude_show_id="other-show"
    )
    assert len(got) == 1
    assert got[0]["show_id"] == "sbb2001-04-27.flac16"
    assert got[0]["cut_sec"] == 100.0
