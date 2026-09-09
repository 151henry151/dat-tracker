"""Tests for the gap-fill listen prompt."""

from dat_tracker.refine_cuts import gap_fill_listen_prompt


def test_gap_fill_listen_prompt_asks_for_inserts():
    prompt = gap_fill_listen_prompt(
        show_id="lke",
        duration_sec=2600.0,
        existing_cuts_sec=[0.0, 404.0, 1070.0, 2600.0],
        windows=[
            {
                "center_sec": 687.0,
                "start_sec": 675.0,
                "end_sec": 699.0,
                "role": "gap_probe",
            }
        ],
    )
    assert "INSERT" in prompt
    assert "REJECT" in prompt
    assert "687" in prompt
    assert "banter" in prompt.lower()
