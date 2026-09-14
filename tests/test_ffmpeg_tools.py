"""Tests for resolving ffmpeg / ffprobe / ffplay binaries."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from dat_tracker.ffmpeg_tools import (
    ffmpeg_bin,
    ffplay_bin,
    ffprobe_bin,
    tool_path,
)


def _exe(name: str) -> str:
    return f"{name}.exe" if sys.platform == "win32" else name


def test_tool_path_prefers_env_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    name = _exe("ffmpeg")
    binary = tmp_path / name
    binary.write_bytes(b"")
    binary.chmod(0o755)
    monkeypatch.setenv("DAT_TRACKER_FFMPEG_DIR", str(tmp_path))
    monkeypatch.setattr("dat_tracker.ffmpeg_tools.shutil.which", lambda *_a, **_k: None)
    assert tool_path("ffmpeg") == str(binary.resolve())


def test_tool_path_falls_back_to_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    name = _exe("ffprobe")
    binary = tmp_path / name
    binary.write_bytes(b"")
    binary.chmod(0o755)
    monkeypatch.delenv("DAT_TRACKER_FFMPEG_DIR", raising=False)
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)

    def fake_which(cmd: str, *args, **kwargs):  # noqa: ANN002, ANN003
        if cmd in (name, "ffprobe"):
            return str(binary)
        return None

    monkeypatch.setattr("dat_tracker.ffmpeg_tools.shutil.which", fake_which)
    assert tool_path("ffprobe") == str(binary)


def test_tool_path_prefers_bundle_over_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    meipass = tmp_path / "meipass"
    bundled = meipass / "ffmpeg" / _exe("ffmpeg")
    bundled.parent.mkdir(parents=True)
    bundled.write_bytes(b"bundle")
    bundled.chmod(0o755)

    monkeypatch.delenv("DAT_TRACKER_FFMPEG_DIR", raising=False)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(meipass), raising=False)
    monkeypatch.setattr(
        "dat_tracker.ffmpeg_tools.shutil.which",
        lambda *_a, **_k: str(tmp_path / "should-not-use"),
    )

    assert tool_path("ffmpeg") == str(bundled.resolve())


def test_helpers_resolve_named_tools(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    for stem in ("ffmpeg", "ffprobe", "ffplay"):
        p = tmp_path / _exe(stem)
        p.write_bytes(b"")
        p.chmod(0o755)
    monkeypatch.setenv("DAT_TRACKER_FFMPEG_DIR", str(tmp_path))
    assert Path(ffmpeg_bin()).name.startswith("ffmpeg")
    assert Path(ffprobe_bin()).name.startswith("ffprobe")
    assert Path(ffplay_bin()).name.startswith("ffplay")


def test_tool_path_raises_when_missing(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("DAT_TRACKER_FFMPEG_DIR", raising=False)
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)
    monkeypatch.setattr("dat_tracker.ffmpeg_tools.shutil.which", lambda *_a, **_k: None)
    monkeypatch.setattr(
        "dat_tracker.ffmpeg_tools._bundle_candidates", lambda _tool: []
    )
    with pytest.raises(FileNotFoundError, match="ffmpeg"):
        tool_path("ffmpeg")
