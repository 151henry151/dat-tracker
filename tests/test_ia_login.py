"""Tests for in-app Archive.org login / config helpers."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from dat_tracker.ia_upload import (
    ia_configured,
    ia_config_path,
    save_ia_login,
)


def test_ia_config_path_prefers_xdg_internetarchive(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    path = ia_config_path()
    assert path == tmp_path / ".config" / "internetarchive" / "ia.ini"


def test_save_ia_login_writes_via_configure(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    cfg = tmp_path / ".config" / "internetarchive" / "ia.ini"
    cfg.parent.mkdir(parents=True)

    def fake_configure(username: str, password: str, config_file: str = "", host: str = "archive.org"):
        assert username == "user@example.com"
        assert password == "secret"
        target = Path(config_file) if config_file else cfg
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("[s3]\naccess = AAA\nsecret = BBB\n")
        return str(target)

    with patch("internetarchive.configure", fake_configure):
        out = save_ia_login("user@example.com", "secret")
    assert Path(out).is_file()
    assert "access = AAA" in Path(out).read_text()
    assert ia_configured()


def test_ia_configured_false_without_keys(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    assert ia_configured() is False
