"""Tests for refining Gemini cut times toward new-track starts."""

from dat_tracker.refine_cuts import (
    rebuild_tracks_from_cuts,
    refine_listen_prompt,
)


def test_rebuild_tracks_from_cuts_preserves_titles_by_index():
    plan = {
        "show_id": "x",
        "duration_sec": 100.0,
        "cuts_sec": [0.0, 40.0, 100.0],
        "tracks": [
            {
                "index": 1,
                "start_sec": 0.0,
                "end_sec": 40.0,
                "track_type": "song",
                "title": "A",
                "segue_into_next": False,
                "confidence": 0.9,
                "evidence": ["old"],
            },
            {
                "index": 2,
                "start_sec": 40.0,
                "end_sec": 100.0,
                "track_type": "banter",
                "title": "B",
                "segue_into_next": False,
                "confidence": 0.8,
                "evidence": ["old"],
            },
        ],
    }
    rebuilt = rebuild_tracks_from_cuts(
        plan,
        [0.0, 45.0, 100.0],
        evidence_by_cut={45.0: ["SNAP_REFINE"]},
    )
    assert rebuilt["cuts_sec"] == [0.0, 45.0, 100.0]
    assert rebuilt["tracks"][0]["end_sec"] == 45.0
    assert rebuilt["tracks"][0]["title"] == "A"
    assert rebuilt["tracks"][1]["start_sec"] == 45.0
    assert rebuilt["tracks"][1]["title"] == "B"
    assert "SNAP_REFINE" in rebuilt["tracks"][1]["evidence"]


def test_refine_listen_prompt_asks_for_new_track_start():
    prompt = refine_listen_prompt(
        show_id="sbb",
        duration_sec=100.0,
        proposed_cuts_sec=[0.0, 40.0, 100.0],
        windows=[
            {
                "center_sec": 40.0,
                "start_sec": 25.0,
                "end_sec": 55.0,
                "role": "candidate",
            }
        ],
    )
    assert "new track begins" in prompt.lower()
    assert "applause" in prompt.lower()
    assert "REJECT" not in prompt or "false" in prompt.lower()
