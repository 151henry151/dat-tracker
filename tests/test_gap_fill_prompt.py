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


def test_gap_fill_listen_prompt_warns_against_jam_solo_false_positives():
    # Real train failure (sbb2001-04-27.flac16): gap-fill inserted a spurious
    # cut into a ~590s continuous blues song with an instrumental/solo
    # section, which Jon tracked as one track. The prompt must tell the model
    # a dynamic shift inside one song (solo, jam, tempo change) is not a
    # track boundary, and require the reason to name a concrete new-track
    # marker rather than accepting on a vague "section change".
    prompt = gap_fill_listen_prompt(
        show_id="sbb",
        duration_sec=1210.0,
        existing_cuts_sec=[0.0, 620.0, 1210.0],
        windows=[
            {
                "center_sec": 865.0,
                "start_sec": 820.0,
                "end_sec": 910.0,
                "role": "gap_probe",
            }
        ],
    )
    assert "solo" in prompt.lower() or "jam" in prompt.lower()
    assert "long" in prompt.lower()
