"""Polish seeded package metadata (spelling / canonical artist names).

Published show.txt headers and dump filenames often carry typos (e.g.
``Jerry Douglass``). Apply deterministic known fixes first; optionally ask
Gemini (text-only) to correct remaining artist/venue/city fields.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable

from dat_tracker.review_plan import migrate_tracking_plan
from dat_tracker.tracking_plan import validate_tracking_plan

_POLISH_NOTE = "Polished package metadata (spelling / canonical names)."

# Whole-word / phrase fixes seen in published etree headers and dump names.
_KNOWN_FIXES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bDouglass\b"), "Douglas"),
    (re.compile(r"\bWilkes Community college\b"), "Wilkes Community College"),
    (
        re.compile(r"\bWilkes community college\b", re.IGNORECASE),
        "Wilkes Community College",
    ),
]

_POLISH_FIELDS = (
    "artist",
    "venue",
    "city",
    "state",
    "notes",
    "set_label",
)


def apply_known_spelling_fixes(text: str) -> str:
    """Apply deterministic community-name spelling fixes to one string."""
    out = text
    for pattern, repl in _KNOWN_FIXES:
        out = pattern.sub(repl, out)
    return out


def _apply_known_to_package(pkg: dict[str, Any]) -> dict[str, str]:
    """Return {field: new_value} for fields that changed under known fixes."""
    changes: dict[str, str] = {}
    for key in _POLISH_FIELDS:
        cur = pkg.get(key)
        if cur in (None, ""):
            continue
        fixed = apply_known_spelling_fixes(str(cur))
        if fixed != str(cur):
            changes[key] = fixed
    return changes


def _gemini_polish_fields(
    fields: dict[str, Any],
    *,
    project_root: Path | None = None,
) -> dict[str, Any]:
    """Ask Gemini Flash (text) to correct obvious spelling / name errors."""
    from google import genai
    from google.genai import types

    from dat_tracker.gemini_tracker import (
        resolve_gemini_api_key,
        resolve_gemini_model,
    )

    root = project_root or Path.cwd()
    key = resolve_gemini_api_key(project_root=root)
    model = resolve_gemini_model(project_root=root)
    client = genai.Client(api_key=key)
    prompt = (
        "You correct metadata for live bluegrass / etree show packages.\n"
        "Given JSON fields (artist, venue, city, state, notes, set_label), "
        "fix only blatant spelling errors and canonical artist name forms "
        "(e.g. Jerry Douglass → Jerry Douglas). "
        "Do not invent missing artists or venues. "
        "Do not change correct values. "
        "Return JSON only with the same keys; omit keys you leave unchanged.\n\n"
        f"INPUT:\n{json.dumps(fields, indent=2)}\n"
    )
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.0,
            response_mime_type="application/json",
            automatic_function_calling=types.AutomaticFunctionCallingConfig(
                disable=True
            ),
        ),
    )
    text = (response.text or "").strip()
    if not text:
        return {}
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        return {}
    return {k: parsed[k] for k in _POLISH_FIELDS if k in parsed and parsed[k]}


def polish_package_metadata(
    plan: dict[str, Any],
    *,
    use_llm: bool = True,
    known_fixes: bool = True,
    project_root: Path | None = None,
    llm_polish_fn: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Correct obvious typos in seeded package fields.

    ``known_fixes`` always runs locally (no network). When ``use_llm`` is true,
    a text Gemini call (or ``llm_polish_fn``) may refine further; LLM failures
    are soft — known fixes still apply.
    """
    plan = migrate_tracking_plan(plan)
    notes = [str(n) for n in (plan.get("notes") or [])]
    already = _POLISH_NOTE in notes
    pkg = dict(plan.get("package") or {})
    changed = False

    if known_fixes:
        for key, value in _apply_known_to_package(pkg).items():
            pkg[key] = value
            changed = True

    # One LLM polish per plan; reopen should not re-hit the API (or warn).
    if use_llm and not already:
        payload = {
            k: pkg.get(k)
            for k in _POLISH_FIELDS
            if pkg.get(k) not in (None, "")
        }
        if payload:
            try:
                fn = llm_polish_fn or (
                    lambda fields: _gemini_polish_fields(
                        fields, project_root=project_root
                    )
                )
                updates = fn(payload)
            except Exception:
                updates = {}
            for key, value in (updates or {}).items():
                if key not in _POLISH_FIELDS:
                    continue
                if value in (None, ""):
                    continue
                if str(pkg.get(key) or "") != str(value):
                    pkg[key] = value
                    changed = True

    plan["package"] = pkg
    if changed and not already:
        notes.append(_POLISH_NOTE)
        plan["notes"] = notes
    validate_tracking_plan(plan)
    return plan
