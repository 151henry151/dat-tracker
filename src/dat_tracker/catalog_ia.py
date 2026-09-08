"""Map Archive.org advancedsearch docs into catalog show rows."""

from __future__ import annotations

from typing import Any


COLLECTION_SUBJECTS = {
    "dave ward collection": "Dave Ward Collection",
    "brian h collection": "Brian H Collection",
}


def _normalize_date(value: str | None) -> str | None:
    if not value:
        return None
    return value[:10]


def _split_coverage(coverage: str | None) -> tuple[str | None, str | None]:
    if not coverage:
        return None, None
    parts = [p.strip() for p in coverage.split(",", 1)]
    if len(parts) == 1:
        return parts[0] or None, None
    return parts[0] or None, parts[1] or None


def _subject_tokens(subjects: list[str] | str | None) -> list[str]:
    if subjects is None:
        return []
    if isinstance(subjects, str):
        subjects = [subjects]
    tokens: list[str] = []
    for subject in subjects:
        # IA sometimes returns one comma-joined subject string.
        for part in subject.split(","):
            token = part.strip().lower()
            if token:
                tokens.append(token)
    return tokens


def _collection_from_subjects(subjects: list[str] | str | None) -> str | None:
    for key in _subject_tokens(subjects):
        if key in COLLECTION_SUBJECTS:
            return COLLECTION_SUBJECTS[key]
    return None


def _prefer_ia_collection(collections: list[str] | str | None) -> str | None:
    if collections is None:
        return None
    if isinstance(collections, str):
        collections = [collections]
    preferred = [c for c in collections if c not in {"etree", "audio_music"} and not c.startswith("fav-")]
    if not preferred:
        return collections[0] if collections else None
    if "taperssection" in preferred and len(preferred) > 1:
        non_taper = [c for c in preferred if c != "taperssection"]
        if non_taper:
            return non_taper[0]
    return preferred[0]


def ia_doc_to_show(doc: dict[str, Any]) -> dict[str, Any]:
    """Convert one IA search document into a catalog show dict."""
    city, state = _split_coverage(doc.get("coverage"))
    collection = _collection_from_subjects(doc.get("subject"))
    if collection is None:
        raise ValueError(f"No Dave/Brian collection subject on {doc.get('identifier')}")
    return {
        "id": doc["identifier"],
        "raw_path": "",
        "artist": doc.get("creator") or "",
        "date": _normalize_date(doc.get("date")) or "",
        "venue": doc.get("venue"),
        "city": city,
        "state": state,
        "collection": collection,
        "status": "already_uploaded",
        "ia_identifier": doc["identifier"],
        "ia_collection": _prefer_ia_collection(doc.get("collection")),
        "source": None,
        "notes": None,
    }


def shows_from_ia_response(payload: dict[str, Any]) -> list[dict[str, Any]]:
    docs = payload.get("response", {}).get("docs", [])
    return [ia_doc_to_show(doc) for doc in docs]
