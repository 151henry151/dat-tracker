# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for a single-file ``dat-review`` operator binary."""

from __future__ import annotations

import platform
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_data_files

block_cipher = None
root = Path(SPECPATH).resolve().parent


def _ffmpeg_platform_dir() -> Path | None:
    system = platform.system()
    machine = platform.machine().lower()
    if system == "Linux":
        key = "linux-x86_64"
    elif system == "Darwin":
        key = "macos-arm64" if machine in ("arm64", "aarch64") else "macos-x86_64"
    elif system == "Windows":
        key = "windows-x86_64"
    else:
        return None
    path = root / "packaging" / "ffmpeg" / key
    return path if path.is_dir() else None


datas = []
binaries = []
hiddenimports = [
    "dat_tracker",
    "dat_tracker.review_cli",
    "dat_tracker.tui_review",
    "dat_tracker.tui_review.app",
    "dat_tracker.tui_review.session",
    "dat_tracker.ffmpeg_tools",
    "textual",
    "textual.widgets",
    "rich",
    "mutagen",
    "internetarchive",
    "jsonschema",
    "google.genai",
    "numpy",
    "soundfile",
    "sounddevice",
]

for pkg in ("textual", "rich", "faster_whisper", "ctranslate2"):
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        pass

try:
    datas += collect_data_files("dat_tracker")
except Exception:
    pass

# Bundle package sources so resources next to the module resolve.
datas += [(str(root / "src" / "dat_tracker"), "dat_tracker")]
# Catalog schema / defaults useful at runtime when present next to checkout;
# frozen apps still work without them (operator picks a dump directory).
if (root / "catalog").is_dir():
    datas += [(str(root / "catalog"), "catalog")]

ffmpeg_dir = _ffmpeg_platform_dir()
if ffmpeg_dir is not None:
    for tool in ("ffmpeg", "ffprobe", "ffplay"):
        for candidate in (ffmpeg_dir / tool, ffmpeg_dir / f"{tool}.exe"):
            if candidate.is_file():
                binaries.append((str(candidate), "ffmpeg"))
                break
    print(f"INFO: Bundling ffmpeg tools from {ffmpeg_dir}")
else:
    print(
        "WARNING: packaging/ffmpeg/<platform>/ missing — "
        "run packaging/fetch_ffmpeg.sh before release builds"
    )

a = Analysis(
    [str(root / "src" / "dat_tracker" / "__main__.py")],
    pathex=[str(root / "src")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="dat-review",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
