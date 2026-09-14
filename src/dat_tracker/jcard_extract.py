"""Gemini vision extract of package fields from dump J-card photos."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable

from dat_tracker.dump_metadata import find_sibling_jcard_images

_JCARD_NOTE = "Extracted package metadata from J-card photo(s) (LLM vision)."

_EXTRACT_FIELDS = (
    "artist",
    "date",
    "venue",
    "city",
    "state",
    "source",
    "transfer",
    "transferer",
    "set_label",
    "notes",
)

_JSON_FENCE = re.compile(
    r"```(?:json)?\s*(\{.*?\})\s*```",
    re.IGNORECASE | re.DOTALL,
)
_JSON_OBJECT = re.compile(r"\{.*\}", re.DOTALL)

VisionFn = Callable[..., dict[str, Any]]


def _parse_json_object(text: str) -> dict[str, Any]:
    raw = (text or "").strip()
    if not raw:
        return {}
    candidates = [raw]
    fence = _JSON_FENCE.search(raw)
    if fence:
        candidates.insert(0, fence.group(1))
    obj = _JSON_OBJECT.search(raw)
    if obj:
        candidates.append(obj.group(0))
    for cand in candidates:
        try:
            data = json.loads(cand)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            return data
    return {}


def _normalize(raw: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in _EXTRACT_FIELDS:
        val = raw.get(key)
        if val in (None, ""):
            continue
        if key == "date":
            text = str(val).strip()
            # Accept M/D/YY handwritten forms from the model.
            m = re.match(r"^(\d{1,2})[/-](\d{1,2})[/-](\d{2}|\d{4})$", text)
            if m:
                mo, dy, yr = int(m.group(1)), int(m.group(2)), int(m.group(3))
                if yr < 100:
                    yr = 2000 + yr if yr < 80 else 1900 + yr
                out["date"] = f"{yr:04d}-{mo:02d}-{dy:02d}"
                continue
            out["date"] = text
            continue
        out[key] = str(val).strip() if not isinstance(val, (list, dict)) else val
    return out


def _jcard_prompt() -> str:
    return (
        "You are reading photos of DAT J-cards / tape labels from a live "
        "bluegrass / jamband collection.\n"
        "Extract show package metadata into JSON with keys: "
        + ", ".join(_EXTRACT_FIELDS)
        + ".\n"
        "Rules:\n"
        "- date as YYYY-MM-DD when you can parse it (e.g. 6-13-03 → 2003-06-13).\n"
        "- artist: expand abbreviations when obvious (BGBrethren → Bluegrass "
        "Brethren). For multi-act tapes, join acts with ' > ' in performance order.\n"
        "- Put tape numbers, circled set indices, radio callsigns, and uncertain "
        "readings into notes — do not invent venue/city/state.\n"
        "- Leave unknown fields null or omit them.\n"
        "- Respond with JSON only.\n"
    )


def _default_vision_llm(
    images: list[Path],
    *,
    project_root: Path | None = None,
) -> dict[str, Any]:
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

    parts: list[Any] = [types.Part.from_text(text=_jcard_prompt())]
    for path in images:
        data = Path(path).read_bytes()
        suffix = Path(path).suffix.lower().lstrip(".") or "jpeg"
        mime = {
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "png": "image/png",
            "webp": "image/webp",
            "tif": "image/tiff",
            "tiff": "image/tiff",
        }.get(suffix, "image/jpeg")
        parts.append(types.Part.from_text(text=f"\nImage file: {Path(path).name}\n"))
        parts.append(types.Part.from_bytes(data=data, mime_type=mime))

    response = client.models.generate_content(
        model=model,
        contents=[types.Content(role="user", parts=parts)],
        config=types.GenerateContentConfig(
            temperature=0.0,
            response_mime_type="application/json",
            max_output_tokens=4096,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(
                disable=True
            ),
        ),
    )
    text = getattr(response, "text", None) or ""
    if not text.strip():
        chunks: list[str] = []
        for cand in getattr(response, "candidates", None) or []:
            content = getattr(cand, "content", None)
            for part in getattr(content, "parts", None) or []:
                t = getattr(part, "text", None)
                if t:
                    chunks.append(t)
        text = "\n".join(chunks)
    return _normalize(_parse_json_object(text))


def extract_package_fields_from_jcards(
    images: list[Path],
    *,
    use_llm: bool = True,
    project_root: Path | None = None,
    llm_vision_fn: VisionFn | None = None,
) -> dict[str, Any]:
    """Vision-extract package fields from one or more J-card images."""
    paths = [Path(p) for p in images if Path(p).is_file()]
    if not paths or not use_llm:
        return {}
    fn = llm_vision_fn or _default_vision_llm
    try:
        raw = fn(paths, project_root=project_root)
    except TypeError:
        raw = fn(paths)
    except Exception:
        return {}
    if not isinstance(raw, dict):
        return {}
    return _normalize(raw)


def jcard_extract_for_audio(
    source_audio: Path,
    *,
    use_llm: bool = True,
    project_root: Path | None = None,
    llm_vision_fn: VisionFn | None = None,
) -> dict[str, Any]:
    """Find sibling J-card images for ``source_audio`` and extract fields."""
    images = find_sibling_jcard_images(Path(source_audio))
    if not images:
        return {}
    return extract_package_fields_from_jcards(
        images,
        use_llm=use_llm,
        project_root=project_root,
        llm_vision_fn=llm_vision_fn,
    )
