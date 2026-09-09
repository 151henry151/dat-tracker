"""Speech snap should not undo a Gemini refine pass by default."""

from dat_tracker.track_show import resolve_speech_snap


def test_resolve_speech_snap_defaults_off_when_refine():
    assert resolve_speech_snap(refine=True, speech_snap=None) is False
    assert resolve_speech_snap(refine=False, speech_snap=None) is True


def test_resolve_speech_snap_honors_explicit_override():
    assert resolve_speech_snap(refine=True, speech_snap=True) is True
    assert resolve_speech_snap(refine=False, speech_snap=False) is False
