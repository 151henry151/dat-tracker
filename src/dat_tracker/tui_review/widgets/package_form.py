"""Package metadata field helpers."""

from __future__ import annotations

from typing import Any

PACKAGE_FIELD_ORDER = (
    "artist",
    "date",
    "venue",
    "city",
    "state",
    "source",
    "transfer",
    "transferer",
    "tracker",
    "set_label",
    "notes",
)


def package_form_values(plan: dict[str, Any]) -> dict[str, str]:
    pkg = plan.get("package") if isinstance(plan.get("package"), dict) else {}
    out: dict[str, str] = {}
    for key in PACKAGE_FIELD_ORDER:
        val = pkg.get(key)
        out[key] = "" if val is None else str(val)
    return out
