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

# Hover tips: purpose + typical Internet Archive / show.txt correspondence.
PACKAGE_FIELD_TOOLTIPS: dict[str, str] = {
    "artist": (
        "Band or artist name. "
        "IA: creator. Also the lead line of show.txt."
    ),
    "date": (
        "Performance date (YYYY-MM-DD). "
        "IA: date. Shown on the item and in show.txt."
    ),
    "venue": (
        "Venue or festival name (e.g. Merlefest). "
        "IA: venue. Written into show.txt under the date."
    ),
    "city": (
        "City of the performance. "
        "IA: with state → coverage (e.g. “Wilkesboro, NC”)."
    ),
    "state": (
        "State / region (e.g. NC). "
        "IA: with city → coverage."
    ),
    "source": (
        "How it was recorded (mic → deck lineage). "
        "IA: source. “Source:” line in show.txt."
    ),
    "transfer": (
        "Transfer path from the master (DAT → interface → FLAC). "
        "IA: lineage. “Transfer:” line in show.txt."
    ),
    "transferer": (
        "Person who transferred the tapes to digital. "
        "IA: transferer. “Transferred by:” in show.txt."
    ),
    "tracker": (
        "Who tracked & uploads this package (you). "
        "IA: credited in description. “Tracked & Uploaded by:” in show.txt."
    ),
    "set_label": (
        "Setlist section heading (usually “One Set” or “Set 1”). "
        "show.txt only — not a separate IA metadata field."
    ),
    "notes": (
        "Free-form notes (stage, lineage quirks, collection). "
        "Often folded into the IA description / show.txt notes."
    ),
}


def package_field_tooltip(key: str) -> str:
    """Return hover text for a package form field."""
    return PACKAGE_FIELD_TOOLTIPS.get(
        key, "Package metadata used when writing show.txt and IA upload fields."
    )


def package_form_values(plan: dict[str, Any]) -> dict[str, str]:
    pkg = plan.get("package") if isinstance(plan.get("package"), dict) else {}
    out: dict[str, str] = {}
    for key in PACKAGE_FIELD_ORDER:
        val = pkg.get(key)
        out[key] = "" if val is None else str(val)
    return out
