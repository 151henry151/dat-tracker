#!/usr/bin/env bash
# Build a single-file dat-review binary with PyInstaller (run from repo root).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

uv sync --extra review --extra asr --extra dev
uv pip install "pyinstaller>=6.0"

bash packaging/fetch_ffmpeg.sh

rm -rf build/pyinstaller dist/pyinstaller
mkdir -p dist/pyinstaller

uv run pyinstaller \
  --noconfirm \
  --clean \
  --distpath dist/pyinstaller \
  --workpath build/pyinstaller \
  packaging/dat-review.spec

echo "Built:"
ls -lh dist/pyinstaller/
