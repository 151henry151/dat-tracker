#!/usr/bin/env python3
"""Review a tracking plan: show picker, Accept-all, or interactive TUI.

Prefer the installed console script::

    dat-review
    dat-review sbb2001-04-27.flac16
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dat_tracker.review_cli import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
