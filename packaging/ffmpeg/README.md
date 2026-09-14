# Bundled ffmpeg binaries (not in git)

Run ``packaging/fetch_ffmpeg.sh`` (or the CI step) to download platform
``ffmpeg`` / ``ffprobe`` / ``ffplay`` into a subdirectory such as
``linux-x86_64/``. PyInstaller picks that folder up when building
``dat-review``.
