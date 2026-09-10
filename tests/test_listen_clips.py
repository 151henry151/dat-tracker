"""Tests for sparse listening windows and Gemini plan parsing."""

import json
from pathlib import Path

import pytest

from dat_tracker.listen_clips import (
    add_gap_probe_centers,
    build_listen_windows,
    extract_audio_clip,
    load_dotenv_file,
    parse_model_json,
    tracking_listen_prompt,
)


def test_build_listen_windows_skips_endpoints_and_clamps():
    windows = build_listen_windows(
        candidate_cuts_sec=[0.0, 12.0, 100.0, 200.0],
        duration_sec=200.0,
        half_window_sec=8.0,
        skip_endpoints=True,
    )
    assert windows == [
        {
            "center_sec": 12.0,
            "start_sec": 4.0,
            "end_sec": 20.0,
            "role": "candidate",
        },
        {
            "center_sec": 100.0,
            "start_sec": 92.0,
            "end_sec": 108.0,
            "role": "candidate",
        },
    ]


def test_build_listen_windows_clamps_near_edges():
    windows = build_listen_windows(
        candidate_cuts_sec=[3.0],
        duration_sec=50.0,
        half_window_sec=8.0,
        skip_endpoints=False,
    )
    assert windows == [
        {
            "center_sec": 3.0,
            "start_sec": 0.0,
            "end_sec": 11.0,
            "role": "candidate",
        }
    ]


def test_add_gap_probe_centers_inserts_probes_in_long_spans():
    # Speech-like anchors only; long music span needs probes near the missed cut.
    centers = add_gap_probe_centers(
        [0.0, 215.0, 375.0, 812.0, 829.0],
        duration_sec=829.0,
        max_gap_sec=240.0,
        probe_step_sec=90.0,
    )
    assert centers[0] == 0.0
    assert centers[-1] == 829.0
    assert 215.0 in centers and 375.0 in centers and 812.0 in centers
    # Opening song span (~215s) is under max_gap → no probes there.
    assert not any(10.0 < c < 200.0 for c in centers)
    probes = [c for c in centers if c not in {0.0, 215.0, 375.0, 812.0, 829.0}]
    assert probes
    assert any(620.0 <= p <= 680.0 for p in probes)


def test_tracking_listen_prompt_requires_rejecting_false_candidates():
    prompt = tracking_listen_prompt(
        show_id="del",
        duration_sec=100.0,
        candidate_cuts_sec=[0.0, 40.0, 100.0],
        windows=[
            {
                "center_sec": 40.0,
                "start_sec": 32.0,
                "end_sec": 48.0,
                "role": "candidate",
            }
        ],
    )
    assert "REJECT" in prompt
    assert "false positive" in prompt.lower() or "false positives" in prompt.lower()
    assert "gap_probe" in prompt or "probe" in prompt.lower()
    assert "banter" in prompt.lower()
    assert "own" in prompt.lower()
    assert "missing a real boundary" in prompt.lower()
    assert "next" in prompt.lower() and "track" in prompt.lower()
    assert "forward_scrub" in prompt
    assert "few-shot" in prompt.lower() or "wrong:" in prompt.lower()
    assert "reject hatch" in prompt.lower() or "inventing a boundary" in prompt.lower()


def test_tracking_listen_prompt_calls_out_segues():
    # Real train over-segmentation (los1997-04-03.kpig): the model correctly
    # heard "song finishes and count-in starts next song" and split there,
    # but Jon's reference kept that pair as one segued track (etree
    # convention: "Song A > Song B" in one file). The old prompt actively
    # told the model to split "two clear song sections with ... count-in
    # between", with no exception for a direct segue (no real pause).
    prompt = tracking_listen_prompt(
        show_id="los",
        duration_sec=100.0,
        candidate_cuts_sec=[0.0, 40.0, 100.0],
        windows=[
            {
                "center_sec": 40.0,
                "start_sec": 32.0,
                "end_sec": 48.0,
                "role": "candidate",
            }
        ],
    )
    assert "segue" in prompt.lower()
    assert "segue_into_next" in prompt


def test_build_listen_windows_adds_forward_scrub_for_candidates():
    # Production merges anchors+probes into candidate_cuts_sec and also passes
    # probe_centers_sec so probes are tagged gap_probe (no forward twin).
    windows = build_listen_windows(
        candidate_cuts_sec=[0.0, 100.0, 200.0, 400.0],
        duration_sec=400.0,
        half_window_sec=8.0,
        skip_endpoints=True,
        probe_centers_sec=[200.0],
        forward_scrub_offset_sec=30.0,
    )
    roles = [(w["role"], float(w["center_sec"])) for w in windows]
    assert ("candidate", 100.0) in roles
    assert ("forward_scrub", 130.0) in roles
    assert ("gap_probe", 200.0) in roles
    assert ("forward_scrub", 230.0) not in roles


def test_parse_model_json_accepts_fenced_block():
    raw = """Here is the plan:
```json
{"cuts_sec": [0.0, 10.0], "overall_confidence": 0.5}
```
"""
    assert parse_model_json(raw) == {"cuts_sec": [0.0, 10.0], "overall_confidence": 0.5}


def test_parse_model_json_raises_on_truncated_object():
    with pytest.raises((json.JSONDecodeError, ValueError)):
        parse_model_json('{"cuts_sec": [0.0, 10.0], "tracks": [{"index": 1')


def test_load_dotenv_file_reads_key(tmp_path: Path):
    env = tmp_path / ".env"
    env.write_text("GEMINI_API_KEY=test-secret\nDAT_TRACKER_LLM_MODEL=gemini-2.5-flash\n")
    vals = load_dotenv_file(env)
    assert vals["GEMINI_API_KEY"] == "test-secret"
    assert vals["DAT_TRACKER_LLM_MODEL"] == "gemini-2.5-flash"


def test_extract_audio_clip_writes_short_flac(tmp_path: Path):
    # 1s mono silence via ffmpeg
    src = tmp_path / "src.flac"
    import subprocess

    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=44100:cl=mono",
            "-t",
            "2",
            str(src),
        ],
        check=True,
        capture_output=True,
    )
    out = tmp_path / "clip.flac"
    extract_audio_clip(src, out, start_sec=0.25, end_sec=0.75)
    assert out.is_file() and out.stat().st_size > 0
