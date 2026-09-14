"""Allow ``python -m dat_tracker`` / PyInstaller entry to launch dat-review."""

from __future__ import annotations

from dat_tracker.review_cli import main

if __name__ == "__main__":
    raise SystemExit(main())
