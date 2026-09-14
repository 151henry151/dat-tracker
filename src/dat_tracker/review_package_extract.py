"""Extract package metadata from companion text / filenames via LLM.

Published info files vary wildly across tapers and eras. Prefer a text Gemini
pass that maps free-form companions into ``plan.package`` fields; fall back to
the heuristic Jon-style parser when the LLM is unavailable or fails.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from dat_tracker.review_hydrate import (
    find_published_show_txt,
    parse_published_show_txt,
)

_EXTRACT_NOTE = "Extracted package metadata from companion files (LLM)."

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


def _gemini_extract_fields(
    context: dict[str, Any],
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
    prompt = (
        "You extract packaging metadata for a live concert FLAC transfer "
        "(etree / Archive.org / Jon King style show.txt).\n"
        "Given companion info text file(s) and nearby filenames, return JSON with "
        "any of these keys you can confidently fill:\n"
        "  artist, date (YYYY-MM-DD), venue, city, state (US 2-letter when possible),\n"
        "  source, transfer, transferer, set_label, notes.\n"
        "Field meanings (important):\n"
        "- source = recording chain to the master (Jon “Source:” line), e.g. "
        "“SBD > DAT” or “SBD > Sony PCM-M1”.\n"
        "- transfer = digitization / encode path from that master to FLAC "
        "(Jon “Transfer:” line), e.g. "
        "“DAT > Sony PCM-2600 > ESI U24XL > Audacity > FLAC”.\n"
        "- transferer = person who did the transfer (“Transferred by:”), "
        "not the tracker/uploader.\n"
        "When the info file has a single combined lineage "
        "(e.g. “SBD > Sony PCM-M1 > Wavelab > CD Wave > FLAC”), split it: "
        "put the capture/deck portion in source and the computer/encode "
        "portion in transfer. Do not leave transfer empty if the lineage "
        "clearly continues into Wavelab/Audacity/FLAC/xACT.\n"
        "When the file already has separate Source: and Transfer: lines, "
        "use those values (strip the labels).\n"
        "Other rules:\n"
        "- Use only information present in the companions; do not invent.\n"
        "- Prefer null/omit over guessing.\n"
        "- venue may combine festival + venue + stage when all are given.\n"
        "- Ignore setlists for field extraction except set_label hints "
        "(One Set / Set 1 / etc.).\n"
        "- Filenames may hint venue (e.g. jamshack) when the text is thin.\n"
        "Return JSON only.\n\n"
        f"CONTEXT:\n{json.dumps(context, indent=2)}\n"
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
    return parsed


def extract_package_fields_from_companions(
    companion_dir: Path,
    *,
    use_llm: bool = True,
    project_root: Path | None = None,
    llm_extract_fn: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Extract package fields from a calibration / companion directory.

    Tries LLM first when ``use_llm``; merges heuristic parser as a soft fill for
    any still-empty keys so Jon-shaped headers keep working offline.
    """
    companion_dir = Path(companion_dir)
    context = gather_companion_sources(companion_dir)
    extracted: dict[str, Any] = {}

    if use_llm and (context["text_files"] or context["filenames"]):
        try:
            fn = llm_extract_fn or (
                lambda ctx: _gemini_extract_fields(ctx, project_root=project_root)
            )
            extracted = _normalize_extracted(fn(context) or {})
        except Exception:
            extracted = {}

    heuristic = _normalize_extracted(_heuristic_extract(companion_dir))
    for key, value in heuristic.items():
        if key not in extracted or extracted.get(key) in (None, ""):
            extracted[key] = value
    return extracted
