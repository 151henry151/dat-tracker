"""Persistent operator defaults for review/package credit fields."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

# Fields collected by `dat-review --setup-defaults` / first-run prompt.
# transfer / transferer / set_label are per-show (or soft built-ins), not dump-wide.
OPERATOR_DEFAULT_KEYS = ("tracker",)

_BUILTIN_FALLBACKS = {
    "set_label": "One Set",
    "tracker": "dat-tracker",
}


def user_defaults_path() -> Path:
    """XDG user config path for review defaults."""
    override = os.environ.get("DAT_TRACKER_DEFAULTS")
    if override:
        return Path(override)
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        base = Path(xdg)
    else:
        base = Path.home() / ".config"
    return base / "dat-tracker" / "review_defaults.json"


def project_defaults_path(project_root: Path | None = None) -> Path:
    root = Path(project_root) if project_root is not None else Path.cwd()
    return root / "catalog" / "operator_defaults.json"


def resolve_defaults_path(*, project_root: Path | None = None) -> Path | None:
    """Return the highest-priority existing defaults file, if any."""
    override = os.environ.get("DAT_TRACKER_DEFAULTS")
    if override:
        path = Path(override)
        return path if path.is_file() else path
    project = project_defaults_path(project_root)
    if project.is_file():
        return project
    user = user_defaults_path()
    if user.is_file():
        return user
    return None


def load_operator_defaults(*, project_root: Path | None = None) -> dict[str, str]:
    """Load operator defaults (env → project catalog → XDG user)."""
    override = os.environ.get("DAT_TRACKER_DEFAULTS")
    candidates: list[Path] = []
    if override:
        candidates.append(Path(override))
    else:
        candidates.append(project_defaults_path(project_root))
        candidates.append(user_defaults_path())

    for path in candidates:
        if not path.is_file():
            continue
        try:
            raw = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(raw, dict):
            continue
        out: dict[str, str] = {}
        for key in OPERATOR_DEFAULT_KEYS:
            val = raw.get(key)
            if val is not None and str(val).strip():
                out[key] = str(val).strip()
        # Prefer this file only when it actually has operator keys; else try next.
        if out:
            return out
    return {}


def defaults_are_configured(*, project_root: Path | None = None) -> bool:
    """True when tracker is set (operator has run setup)."""
    loaded = load_operator_defaults(project_root=project_root)
    return bool(loaded.get("tracker"))


def save_operator_defaults(
    fields: dict[str, Any],
    *,
    project_root: Path | None = None,
    path: Path | None = None,
    prefer_project: bool = False,
) -> Path:
    """Write defaults; prefer explicit path, else env, else XDG (or project if asked)."""
    if path is None:
        override = os.environ.get("DAT_TRACKER_DEFAULTS")
        if override:
            path = Path(override)
        elif prefer_project and project_root is not None:
            path = project_defaults_path(project_root)
        else:
            path = user_defaults_path()
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing: dict[str, Any] = {}
    if path.is_file():
        try:
            existing = json.loads(path.read_text())
            if not isinstance(existing, dict):
                existing = {}
        except (OSError, json.JSONDecodeError):
            existing = {}
    # Drop legacy dump-wide keys; those belong on each show.
    for legacy in ("transfer", "transferer", "set_label"):
        existing.pop(legacy, None)
    for key in OPERATOR_DEFAULT_KEYS:
        if key not in fields:
            continue
        val = fields[key]
        if val is None or (isinstance(val, str) and not val.strip()):
            existing.pop(key, None)
        else:
            existing[key] = str(val).strip()
    path.write_text(json.dumps(existing, indent=2) + "\n")
    return path


def merge_builtin_fallbacks(defaults: dict[str, str]) -> dict[str, str]:
    """Apply soft built-ins (e.g. set_label=One Set) without clobbering user values."""
    out = dict(defaults)
    for key, val in _BUILTIN_FALLBACKS.items():
        if not out.get(key):
            out[key] = val
    return out
