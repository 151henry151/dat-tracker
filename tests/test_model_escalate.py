"""Tests for Flash→Pro model escalation helpers."""

from dat_tracker.gemini_tracker import (
    DEFAULT_GEMINI_FLASH_MODEL,
    DEFAULT_GEMINI_PRO_MODEL,
    resolve_gemini_model,
    resolve_escalate_model,
)


def test_default_models_are_named():
    assert "flash" in DEFAULT_GEMINI_FLASH_MODEL
    assert "pro" in DEFAULT_GEMINI_PRO_MODEL


def test_resolve_escalate_model_uses_pro_when_requested(monkeypatch, tmp_path):
    monkeypatch.delenv("DAT_TRACKER_LLM_MODEL", raising=False)
    monkeypatch.delenv("DAT_TRACKER_LLM_PRO_MODEL", raising=False)
    (tmp_path / ".env").write_text("")
    assert (
        resolve_escalate_model(project_root=tmp_path, escalate=True)
        == DEFAULT_GEMINI_PRO_MODEL
    )
    assert (
        resolve_escalate_model(project_root=tmp_path, escalate=False)
        == resolve_gemini_model(project_root=tmp_path)
    )
