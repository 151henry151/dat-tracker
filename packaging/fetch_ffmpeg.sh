#!/usr/bin/env bash
# Download static ffmpeg/ffprobe/ffplay into packaging/ffmpeg/<platform>/ for bundling.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT_ROOT="${DAT_TRACKER_FFMPEG_CACHE:-$ROOT/packaging/ffmpeg}"
mkdir -p "$OUT_ROOT"

os="$(uname -s)"
arch="$(uname -m)"
case "$os" in
  Linux)
    platform="linux-x86_64"
    if [[ "$arch" != "x86_64" && "$arch" != "amd64" ]]; then
      echo "Unsupported Linux arch: $arch (need x86_64 static build)" >&2
      exit 1
    fi
    url="https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz"
    ;;
  Darwin)
    if [[ "$arch" == "arm64" ]]; then
      platform="macos-arm64"
      # Evermeet provides Intel builds; on Apple Silicon use Homebrew binaries when present.
      if command -v brew >/dev/null 2>&1; then
        brew_prefix="$(brew --prefix ffmpeg 2>/dev/null || true)"
        if [[ -n "$brew_prefix" && -x "$brew_prefix/bin/ffmpeg" ]]; then
          dest="$OUT_ROOT/$platform"
          mkdir -p "$dest"
          for tool in ffmpeg ffprobe ffplay; do
            cp -f "$brew_prefix/bin/$tool" "$dest/$tool"
            chmod +x "$dest/$tool"
          done
          echo "Copied Homebrew ffmpeg into $dest"
          ls -lh "$dest"
          exit 0
        fi
      fi
      echo "Install ffmpeg with Homebrew (brew install ffmpeg), then re-run." >&2
      exit 1
    else
      platform="macos-x86_64"
      url="https://evermeet.cx/ffmpeg/getrelease/ffmpeg/zip"
      # evermeet ships one zip per tool; handle below specially
    fi
    ;;
  MINGW*|MSYS*|CYGWIN*|Windows_NT)
    platform="windows-x86_64"
    url="https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
    ;;
  *)
    echo "Unsupported OS: $os" >&2
    exit 1
    ;;
esac

dest="$OUT_ROOT/$platform"
tmpdir="$(mktemp -d)"
cleanup() { rm -rf "$tmpdir"; }
trap cleanup EXIT

echo "Fetching ffmpeg for $platform…"
archive="$tmpdir/ffmpeg-download"
case "$os" in
  Linux)
    curl -fsSL "$url" -o "$archive.tar.xz"
    tar -xJf "$archive.tar.xz" -C "$tmpdir"
    src_dir="$(find "$tmpdir" -type d -name 'ffmpeg-*-amd64-static' | head -1)"
    mkdir -p "$dest"
    for tool in ffmpeg ffprobe; do
      cp -f "$src_dir/$tool" "$dest/$tool"
      chmod +x "$dest/$tool"
    done
    # Static linux builds often omit ffplay (needs SDL); copy if present, else
    # dat-review falls back to sounddevice for playback.
    if [[ -x "$src_dir/ffplay" ]]; then
      cp -f "$src_dir/ffplay" "$dest/ffplay"
      chmod +x "$dest/ffplay"
    fi
    ;;
  Darwin)
    if [[ "$arch" != "arm64" ]]; then
      mkdir -p "$dest" "$tmpdir/unz"
      for tool in ffmpeg ffprobe ffplay; do
        curl -fsSL "https://evermeet.cx/ffmpeg/getrelease/${tool}/zip" -o "$tmpdir/${tool}.zip"
        unzip -qo "$tmpdir/${tool}.zip" -d "$tmpdir/unz"
        cp -f "$tmpdir/unz/$tool" "$dest/$tool"
        chmod +x "$dest/$tool"
      done
    fi
    ;;
  MINGW*|MSYS*|CYGWIN*|Windows_NT)
    curl -fsSL "$url" -o "$archive.zip"
    unzip -qo "$archive.zip" -d "$tmpdir/unz"
    bin_dir="$(find "$tmpdir/unz" -type d -name bin | head -1)"
    mkdir -p "$dest"
    for tool in ffmpeg ffprobe ffplay; do
      cp -f "$bin_dir/${tool}.exe" "$dest/${tool}.exe"
    done
    ;;
esac

echo "Bundled tools in $dest:"
ls -lh "$dest"
