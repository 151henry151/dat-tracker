"""Resolve ffmpeg / ffprobe / ffplay for subprocess calls.

Frozen PyInstaller builds may ship static binaries under ``_MEIPASS/ffmpeg/``.
Dev checkouts fall back to ``DAT_TRACKER_FFMPEG_DIR`` then ``PATH``.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


def _exe_name(tool: str) -> str:
    if sys.platform == "win32" and not tool.lower().endswith(".exe"):
        return f"{tool}.exe"
    return tool


def _bundle_candidates(tool: str) -> list[Path]:
    name = _exe_name(tool)
    candidates: list[Path] = []
    meipass = getattr(sys, "_MEIPASS", None)
    if getattr(sys, "frozen", False) and meipass:
        root = Path(meipass)
        candidates.append(root / "ffmpeg" / name)
        candidates.append(root / name)
    # One-dir / side-by-side layout next to a frozen (or renamed) dat-review binary.
    try:
        exe = Path(sys.executable).resolve()
        if getattr(sys, "frozen", False) or exe.name.startswith("dat-review"):
            exe_dir = exe.parent
            candidates.append(exe_dir / "ffmpeg" / name)
            candidates.append(exe_dir / name)
    except Exception:
        pass
    return candidates


def tool_path(tool: str) -> str:
    """Return an absolute path to ``ffmpeg``, ``ffprobe``, or ``ffplay``.

    Search order:
    1. ``DAT_TRACKER_FFMPEG_DIR`` / tool
    2. Bundled next to a frozen app (``_MEIPASS/ffmpeg/…``)
    3. ``PATH`` via ``shutil.which``
    """
    name = _exe_name(tool)
    env_dir = os.environ.get("DAT_TRACKER_FFMPEG_DIR", "").strip()
    if env_dir:
        candidate = Path(env_dir) / name
        if candidate.is_file():
            return str(candidate.resolve())

    for candidate in _bundle_candidates(tool):
        if candidate.is_file():
            return str(candidate.resolve())

    found = shutil.which(name) or shutil.which(tool)
    if found:
        return found

    raise FileNotFoundError(
        f"{tool} not found. Install ffmpeg on PATH, set DAT_TRACKER_FFMPEG_DIR, "
        "or use a dat-review release that bundles ffmpeg."
    )


def ffmpeg_bin() -> str:
    return tool_path("ffmpeg")


def ffprobe_bin() -> str:
    return tool_path("ffprobe")


def ffplay_bin() -> str:
    return tool_path("ffplay")
