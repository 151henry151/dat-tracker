"""Tests for first-run Gemini API key prompt helpers and TUI screen."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from dat_tracker.gemini_tracker import (
    gemini_api_key_is_configured,
    resolve_gemini_api_key,
    save_gemini_api_key,
)


def test_gemini_api_key_is_configured_from_env(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    assert gemini_api_key_is_configured(project_root=tmp_path) is False
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    assert gemini_api_key_is_configured(project_root=tmp_path) is True


def test_save_gemini_api_key_writes_dotenv(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    path = save_gemini_api_key("abc123", project_root=tmp_path)
    assert path == tmp_path / ".env"
    text = path.read_text()
    assert "GEMINI_API_KEY=abc123" in text
    assert gemini_api_key_is_configured(project_root=tmp_path) is True
    assert resolve_gemini_api_key(project_root=tmp_path) == "abc123"


def test_save_gemini_api_key_preserves_other_dotenv_keys(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    (tmp_path / ".env").write_text("DAT_TRACKER_LLM_MODEL=gemini-x\nFOO=bar\n")
    save_gemini_api_key("newkey", project_root=tmp_path)
    text = (tmp_path / ".env").read_text()
    assert "DAT_TRACKER_LLM_MODEL=gemini-x" in text
    assert "FOO=bar" in text
    assert "GEMINI_API_KEY=newkey" in text


def test_session_prompts_gemini_key_when_missing(tmp_path: Path, monkeypatch):
    pytest.importorskip("textual")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setenv("DAT_TRACKER_DEFAULTS", str(tmp_path / "defaults.json"))
    (tmp_path / "defaults.json").write_text('{"tracker": "Tester"}\n')

    from dat_tracker.tui_review.dump_root import DumpRootScreen
    from dat_tracker.tui_review.gemini_key_setup import GeminiApiKeyScreen
    from dat_tracker.tui_review.session import ReviewSessionApp

    app = ReviewSessionApp(
        shows=[],
        project_root=tmp_path,
        dump_first=True,
        prompt_defaults=True,
        prompt_gemini_key=True,
    )

    async def run() -> None:
        async with app.run_test() as pilot:
            await pilot.pause()
            assert isinstance(app.screen, GeminiApiKeyScreen)
            app.screen.action_skip()
            for _ in range(40):
                if isinstance(app.screen, DumpRootScreen):
                    break
                await pilot.pause(0.05)
            assert isinstance(app.screen, DumpRootScreen)

    asyncio.run(run())
