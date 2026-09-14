"""Extract package metadata from companion text / filenames via LLM.

Published info files vary wildly across tapers and eras. Prefer a text Gemini
pass that interprets free-form companions into ``plan.package`` fields. When
location fields are still blank but artist + date are known, optionally run a
second Gemini call with Google Search grounding to research venue/city/state.

Heuristic Jon-style parsing is an offline fallback only (LLM unavailable or
total failure)—not a soft fill after a successful LLM pass.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable

from dat_tracker.review_hydrate import (
    find_published_show_txt,
    parse_published_show_txt,
)

_EXTRACT_NOTE = "Extracted package metadata from companion files (LLM)."
_RESEARCH_NOTE = "Researched missing package location fields (LLM + web)."

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

# Safe to fill from public setlists / show databases — never invent lineage.
_RESEARCHABLE_FIELDS = ("venue", "city", "state")

_SKIP_TXT_SUBSTR = (
    "ffp",
    "fingerprint",
    "concat",
    "known_cuts",
    "whisper",
    "tracking_plan",
    "waveform",
)

_AUDIO_SUFFIXES = {".flac", ".wav", ".mp3", ".ogg", ".m4a"}
_JSON_FENCE = re.compile(
    r"```(?:json)?\s*(\{.*?\})\s*```",
    re.IGNORECASE | re.DOTALL,
)
_JSON_OBJECT = re.compile(r"\{.*\}", re.DOTALL)


def gather_companion_sources(
    companion_dir: Path,
    *,
    max_chars_per_file: int = 12_000,
) -> dict[str, Any]:
    """Collect companion ``.txt`` bodies and nearby filenames for LLM context."""
    companion_dir = Path(companion_dir)
    text_files: list[dict[str, str]] = []
    filenames: list[str] = []
    if not companion_dir.is_dir():
        return {
            "directory": str(companion_dir),
            "text_files": text_files,
            "filenames": filenames,
        }

    for path in sorted(companion_dir.iterdir()):
        if not path.is_file():
            continue
        name = path.name
        filenames.append(name)
        if path.suffix.lower() != ".txt":
            continue
        lower = name.lower()
        if any(s in lower for s in _SKIP_TXT_SUBSTR):
            continue
        try:
            text = path.read_text(errors="replace")
        except OSError:
            continue
        if len(text) > max_chars_per_file:
            text = text[:max_chars_per_file] + "\n…[truncated]…"
        text_files.append({"name": name, "text": text})

    # Prefer audio-ish names first in the prompt (venue tokens often appear there).
    filenames.sort(
        key=lambda n: (0 if Path(n).suffix.lower() in _AUDIO_SUFFIXES else 1, n.lower())
    )
    return {
        "directory": str(companion_dir),
        "text_files": text_files,
        "filenames": filenames,
    }


def _heuristic_extract(companion_dir: Path) -> dict[str, Any]:
    txt = find_published_show_txt(companion_dir)
    if txt is None:
        return {}
    return parse_published_show_txt(txt)


def parse_json_object(text: str) -> dict[str, Any]:
    """Best-effort parse of a JSON object from model text (fences / prose ok)."""
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
            parsed = json.loads(cand)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return {}


def _normalize_extracted(raw: dict[str, Any]) -> dict[str, Any]:
    """Keep only known package keys; drop empties; normalize state codes lightly."""
    from dat_tracker.review_hydrate import _normalize_state, _parse_date_line

    out: dict[str, Any] = {}
    for key in _EXTRACT_FIELDS:
        if key not in raw:
            continue
        val = raw[key]
        if val in (None, ""):
            continue
        if isinstance(val, list):
            # notes sometimes returned as list of strings
            val = "; ".join(str(x).strip() for x in val if str(x).strip())
            if not val:
                continue
        text = str(val).strip()
        if not text:
            continue
        if key == "date":
            iso = _parse_date_line(text) or text
            # Accept already-ISO yyyy-mm-dd
            if len(iso) == 10 and iso[4] == "-" and iso[7] == "-":
                out[key] = iso
            elif _parse_date_line(iso):
                out[key] = _parse_date_line(iso)
            else:
                out[key] = text
            continue
        if key == "state":
            out[key] = _normalize_state(text)
            continue
        out[key] = text
    return out


def build_gemini_generate_config(*, with_google_search: bool):
    """Build GenerateContentConfig; search and JSON mime are mutually exclusive."""
    from google.genai import types

    if with_google_search:
        return types.GenerateContentConfig(
            temperature=0.0,
            tools=[types.Tool(google_search=types.GoogleSearch())],
            automatic_function_calling=types.AutomaticFunctionCallingConfig(
                disable=True
            ),
        )
    return types.GenerateContentConfig(
        temperature=0.0,
        response_mime_type="application/json",
        automatic_function_calling=types.AutomaticFunctionCallingConfig(
            disable=True
        ),
    )


def _companion_extract_prompt(context: dict[str, Any]) -> str:
    return (
        "You extract packaging metadata for a live concert FLAC transfer "
        "(etree / Archive.org / Jon King style show.txt).\n"
        "Given companion info text file(s) and nearby filenames, interpret the "
        "messy human text and return JSON with any of these keys you can fill:\n"
        "  artist, date (YYYY-MM-DD), venue, city, state (US 2-letter when possible),\n"
        "  source, transfer, transferer, set_label, notes.\n"
        "Field meanings (important):\n"
        "- source = recording chain to the master (Jon “Source:” line), e.g. "
        "“SBD > DAT” or “SBD > Sony PCM-M1”.\n"
        "- transfer = digitization / encode path from that master to FLAC "
        "(Jon “Transfer:” / “Lineage:” line), e.g. "
        "“DAT > Sony PCM-2600 > ESI U24XL > Audacity > FLAC”.\n"
        "- transferer = person who did the transfer (“Transferred by:”), "
        "not the tracker/uploader.\n"
        "When the info file has a single combined lineage "
        "(e.g. “SBD > Sony PCM-M1 > Wavelab > CD Wave > FLAC”), split it: "
        "put the capture/deck portion in source and the computer/encode "
        "portion in transfer. Do not leave transfer empty if the lineage "
        "clearly continues into Wavelab/Audacity/FLAC/xACT.\n"
        "When the file already has separate Source: and Transfer:/Lineage: "
        "lines (even after the setlist), use those values (strip the labels).\n"
        "Interpretation rules:\n"
        "- Read past typos and odd layouts (misspelled months, blank lines, "
        "“Venue: …” prefixes, festival + stage stacks, source after setlist).\n"
        "- Normalize dates to YYYY-MM-DD even when the text has typos "
        "(e.g. “Febuary, 24, 2007” → 2007-02-24).\n"
        "- Prefer the physical venue/stage when both a festival name and a "
        "venue/stage are given; put the festival in notes if helpful.\n"
        "- Fix obvious artist/venue spelling when the intended name is clear "
        "from context (Douglass→Douglas), but do not invent missing lineage.\n"
        "- Prefer null/omit over guessing lineage, credits, or locations that "
        "are not supported by the companions or filenames.\n"
        "- Ignore setlists for field extraction except set_label hints "
        "(One Set / Set 1 / etc.).\n"
        "- Filenames may hint venue (e.g. jamshack) when the text is thin.\n"
        "Return JSON only.\n\n"
        f"CONTEXT:\n{json.dumps(context, indent=2)}\n"
    )


def _research_missing_prompt(
    partial: dict[str, Any],
    context: dict[str, Any],
    missing: list[str],
) -> str:
    return (
        "You are filling missing live-concert packaging fields for an etree / "
        "Archive.org show package.\n"
        f"Missing fields to research: {', '.join(missing)}.\n"
        "You may use Google Search. Prefer setlist databases, etree, Archive.org, "
        "band sites, and contemporary reviews.\n"
        "Only fill fields you can support with a clear public match on artist + "
        "date (and city if already known). If uncertain, omit the field.\n"
        "Never invent or alter source / transfer / transferer / lineage.\n"
        "Return a JSON object with only the missing keys you can fill "
        "(venue, city, state as applicable). dates must be YYYY-MM-DD if you "
        "return date. US states as 2-letter codes when possible.\n\n"
        f"KNOWN_FIELDS:\n{json.dumps(partial, indent=2)}\n\n"
        f"COMPANION_CONTEXT:\n{json.dumps(context, indent=2)}\n"
    )


def _gemini_extract_fields(
    context: dict[str, Any],
    *,
    project_root: Path | None = None,
) -> dict[str, Any]:
    from google import genai

    from dat_tracker.gemini_tracker import (
        resolve_gemini_api_key,
        resolve_gemini_model,
    )

    root = project_root or Path.cwd()
    key = resolve_gemini_api_key(project_root=root)
    model = resolve_gemini_model(project_root=root)
    client = genai.Client(api_key=key)
    response = client.models.generate_content(
        model=model,
        contents=_companion_extract_prompt(context),
        config=build_gemini_generate_config(with_google_search=False),
    )
    return parse_json_object(response.text or "")


def _gemini_research_missing_fields(
    partial: dict[str, Any],
    context: dict[str, Any],
    *,
    project_root: Path | None = None,
) -> dict[str, Any]:
    from google import genai

    from dat_tracker.gemini_tracker import (
        resolve_gemini_api_key,
        resolve_gemini_model,
    )

    missing = [
        k for k in _RESEARCHABLE_FIELDS if partial.get(k) in (None, "")
    ]
    if not missing:
        return {}
    if partial.get("artist") in (None, "") or partial.get("date") in (None, ""):
        return {}

    root = project_root or Path.cwd()
    key = resolve_gemini_api_key(project_root=root)
    model = resolve_gemini_model(project_root=root)
    client = genai.Client(api_key=key)
    response = client.models.generate_content(
        model=model,
        contents=_research_missing_prompt(partial, context, missing),
        config=build_gemini_generate_config(with_google_search=True),
    )
    researched = parse_json_object(response.text or "")
    # Never allow research to invent lineage.
    return {k: researched[k] for k in _RESEARCHABLE_FIELDS if k in researched}


def _needs_location_research(fields: dict[str, Any]) -> bool:
    if fields.get("artist") in (None, "") or fields.get("date") in (None, ""):
        return False
    return any(fields.get(k) in (None, "") for k in _RESEARCHABLE_FIELDS)


def extract_package_fields_from_companions(
    companion_dir: Path,
    *,
    use_llm: bool = True,
    allow_web_research: bool = True,
    project_root: Path | None = None,
    llm_extract_fn: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    llm_research_fn: (
        Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]] | None
    ) = None,
    result_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Extract package fields from a calibration / companion directory.

    LLM-first: interpret companions with Gemini. Optionally research missing
    venue/city/state via Google Search when artist + date are known. Heuristic
    parse runs only when the LLM is disabled or returns nothing.
    """
    companion_dir = Path(companion_dir)
    context = gather_companion_sources(companion_dir)
    extracted: dict[str, Any] = {}
    llm_ok = False
    used_research = False

    if use_llm and (context["text_files"] or context["filenames"]):
        try:
            fn = llm_extract_fn or (
                lambda ctx: _gemini_extract_fields(ctx, project_root=project_root)
            )
            extracted = _normalize_extracted(fn(context) or {})
            llm_ok = bool(extracted)
        except Exception:
            extracted = {}
            llm_ok = False

        if (
            llm_ok
            and allow_web_research
            and _needs_location_research(extracted)
        ):
            try:
                research_fn = llm_research_fn or (
                    lambda partial, ctx: _gemini_research_missing_fields(
                        partial, ctx, project_root=project_root
                    )
                )
                researched = _normalize_extracted(
                    research_fn(extracted, context) or {}
                )
            except Exception:
                researched = {}
            for key in _RESEARCHABLE_FIELDS:
                if extracted.get(key) in (None, "") and researched.get(key):
                    extracted[key] = researched[key]
                    used_research = True

    if not llm_ok:
        heuristic = _normalize_extracted(_heuristic_extract(companion_dir))
        for key, value in heuristic.items():
            if key not in extracted or extracted.get(key) in (None, ""):
                extracted[key] = value

    if result_meta is not None:
        result_meta["used_llm"] = bool(llm_ok)
        result_meta["used_research"] = bool(used_research)
    return extracted
