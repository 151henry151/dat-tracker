"""Retries for transient Gemini transport failures."""

from types import SimpleNamespace

import httpx
import pytest

from dat_tracker.gemini_tracker import _generate_content_with_retries


def test_generate_content_retries_ssl_read_errors(monkeypatch):
    calls = {"n": 0}

    class _Models:
        def generate_content(self, **_kwargs):
            calls["n"] += 1
            if calls["n"] < 3:
                raise httpx.ReadError("SSLV3_ALERT_BAD_RECORD_MAC")
            return SimpleNamespace(text='{"cuts_sec": [0.0, 1.0]}')

    class _Client:
        models = _Models()

    sleeps: list[float] = []
    monkeypatch.setattr("time.sleep", sleeps.append)

    out = _generate_content_with_retries(
        client=_Client(),
        model_name="fake",
        parts=[],
        max_retries=5,
    )
    assert calls["n"] == 3
    assert out.text.startswith("{")
    assert sleeps


def test_generate_content_raises_after_exhausted_transport_retries(monkeypatch):
    class _Models:
        def generate_content(self, **_kwargs):
            raise httpx.ReadError("boom")

    class _Client:
        models = _Models()

    monkeypatch.setattr("time.sleep", lambda *_a, **_k: None)
    with pytest.raises(httpx.ReadError):
        _generate_content_with_retries(
            client=_Client(),
            model_name="fake",
            parts=[],
            max_retries=2,
        )
