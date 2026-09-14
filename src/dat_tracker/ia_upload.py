"""Archive.org upload helpers for finished etree packages."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from dat_tracker.review_plan import package_fields_from_plan

DEFAULT_IA_COLLECTION = "taperssection"


@dataclass
class UploadResult:
    ok: bool
    identifier: str
    item_url: str | None = None
    error: str | None = None


def build_ia_metadata(
    plan: dict[str, Any],
    *,
    collection: str = DEFAULT_IA_COLLECTION,
    identifier: str | None = None,
) -> dict[str, Any]:
    """Map approved plan.package fields into internetarchive metadata."""
    pkg = package_fields_from_plan(plan)
    show_id = identifier or str(plan.get("show_id") or "")
    artist = str(pkg.get("artist") or "Unknown Artist")
    date = str(pkg.get("date") or "")
    venue = str(pkg.get("venue") or "")
    city = pkg.get("city")
    state = pkg.get("state")
    coverage_parts = [p for p in (city, state) if p not in (None, "")]
    coverage = ", ".join(str(p) for p in coverage_parts)

    title_bits = [artist]
    if date:
        title_bits.append(date)
    if venue:
        title_bits.append(venue)
    title = " - ".join(title_bits)

    source = str(pkg.get("source") or "")
    transfer = str(pkg.get("transfer") or "")
    transferer = str(pkg.get("transferer") or "")
    tracker = str(pkg.get("tracker") or "")
    lineage_parts = [p for p in (source, transfer) if p]
    lineage = " > ".join(lineage_parts) if lineage_parts else ""
    if transferer:
        lineage = (
            f"{lineage}; Transferred by {transferer}"
            if lineage
            else f"Transferred by {transferer}"
        )
    if tracker:
        lineage = (
            f"{lineage}; Tracked & Uploaded by {tracker}"
            if lineage
            else f"Tracked & Uploaded by {tracker}"
        )

    subjects: list[str] = []
    for s in pkg.get("collection_subjects") or []:
        text = str(s).strip()
        if text and text not in subjects:
            subjects.append(text)
    if artist and artist not in subjects:
        subjects.append(artist)

    meta: dict[str, Any] = {
        "identifier": show_id,
        "mediatype": "audio",
        "collection": [collection],
        "creator": artist,
        "title": title,
        "subject": subjects,
    }
    if date:
        meta["date"] = date
    if venue:
        meta["venue"] = venue
    if coverage:
        meta["coverage"] = coverage
    if source:
        meta["source"] = source
    if lineage:
        meta["lineage"] = lineage
    if transferer:
        meta["transferer"] = transferer
    if tracker:
        meta["taper"] = tracker  # IA “taper” often holds tracker credit for etree
    return meta


def _catalog_paths(project_root: Path) -> list[Path]:
    return [
        project_root / "catalog" / "shows.json",
        project_root / "catalog" / "calibration_tier_b.json",
        project_root / "catalog" / "calibration_tier_a.json",
    ]


def catalog_blocks_upload(
    show_id: str,
    *,
    project_root: Path | None = None,
) -> bool:
    """True when catalog marks this show already_uploaded (do not re-upload)."""
    root = Path(project_root) if project_root is not None else Path.cwd()
    for path in _catalog_paths(root):
        if not path.is_file():
            continue
        try:
            doc = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        for row in doc.get("shows") or []:
            if str(row.get("id")) != show_id:
                continue
            if str(row.get("status") or "") == "already_uploaded":
                return True
    return False


def ia_config_path() -> Path:
    """Return the preferred path for ``ia.ini`` (XDG / internetarchive layout)."""
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg and Path(xdg).is_absolute():
        return Path(xdg) / "internetarchive" / "ia.ini"
    home = Path.home()
    modern = home / ".config" / "internetarchive" / "ia.ini"
    legacy = home / ".config" / "ia.ini"
    if modern.is_file():
        return modern
    if legacy.is_file():
        return legacy
    return modern


def ia_configured() -> bool:
    """True when internetarchive appears to have S3 credentials configured."""
    # Environment variables (library may honor these).
    if os.environ.get("IA_ACCESS_KEY_ID") and os.environ.get("IA_SECRET_ACCESS_KEY"):
        return True
    path = ia_config_path()
    if path.is_file():
        text = path.read_text(errors="replace")
        if "access" in text.lower() and "secret" in text.lower():
            # crude but avoids importing a broken session
            if re.search(r"(?im)^\s*access\s*=\s*\S+", text) and re.search(
                r"(?im)^\s*secret\s*=\s*\S+", text
            ):
                return True
    try:
        session = _get_ia_session()
    except Exception:
        return False
    config = getattr(session, "config", None) or {}
    if isinstance(config, dict):
        s3 = config.get("s3") or {}
        if isinstance(s3, dict) and s3.get("access") and s3.get("secret"):
            return True
    return False


def save_ia_login(
    email: str,
    password: str,
    *,
    config_file: str | Path | None = None,
) -> str:
    """Log in to Archive.org and write IA-S3 keys (same as ``ia configure``).

    Returns the path to the written config file.
    """
    import internetarchive as ia

    email = email.strip()
    if not email or not password:
        raise ValueError("Email and password are required.")
    target = str(config_file) if config_file else str(ia_config_path())
    Path(target).parent.mkdir(parents=True, exist_ok=True)
    return ia.configure(email, password, config_file=target)


def _get_ia_session():
    import internetarchive as ia

    return ia.get_session()


def identifier_exists(identifier: str) -> bool:
    """Return True if an Archive.org item with this identifier already exists."""
    import internetarchive as ia

    try:
        item = ia.get_item(identifier)
        # exists when metadata has an identifier / files
        meta = getattr(item, "metadata", None) or {}
        if meta.get("identifier"):
            return True
        files = getattr(item, "files", None)
        return bool(files)
    except Exception:
        return False


def upload_package(
    package_dir: Path,
    *,
    identifier: str,
    metadata: dict[str, Any],
    progress: Callable[[str], None] | None = None,
    on_progress: Callable[[str, float], None] | None = None,
    project_root: Path | None = None,
    skip_existence_check: bool = False,
) -> UploadResult:
    """Upload files in package_dir to Archive.org under identifier.

    Prefer ``on_progress(message, fraction)``. Legacy ``progress(message)``
    still receives stage text. Large uploads pulse an elapsed heartbeat so
    the UI does not look hung while a single file transfers.
    """
    from dat_tracker.progress_util import emit_progress, progress_heartbeat

    package_dir = Path(package_dir)
    if not package_dir.is_dir():
        return UploadResult(
            ok=False, identifier=identifier, error=f"missing package dir {package_dir}"
        )

    if catalog_blocks_upload(identifier, project_root=project_root):
        return UploadResult(
            ok=False,
            identifier=identifier,
            error=(
                f"Catalog marks {identifier!r} as already_uploaded; "
                "refusing to upload a competing item."
            ),
        )

    if not ia_configured():
        return UploadResult(
            ok=False,
            identifier=identifier,
            error="Archive.org CLI not configured (run: ia configure).",
        )

    if not skip_existence_check and identifier_exists(identifier):
        return UploadResult(
            ok=False,
            identifier=identifier,
            error=f"Archive.org item {identifier!r} already exists.",
        )

    files = sorted(
        p for p in package_dir.iterdir() if p.is_file() and not p.name.startswith(".")
    )
    if not files:
        return UploadResult(
            ok=False, identifier=identifier, error="package directory has no files"
        )

    def report(message: str, fraction: float) -> None:
        emit_progress(on_progress, message, fraction)
        if progress is not None:
            progress(message)

    combined = report if (on_progress is not None or progress is not None) else None
    n = len(files)
    report(f"Uploading {n} files as {identifier}…", 0.05)
    session = _get_ia_session()
    # Drop identifier from metadata body — passed as item name.
    meta = {k: v for k, v in metadata.items() if k != "identifier"}
    try:
        for i, path in enumerate(files):
            frac = 0.08 + 0.85 * (i / max(n, 1))
            label = f"Uploading {path.name} ({i + 1}/{n})"
            file_meta = meta if i == 0 else {}
            with progress_heartbeat(
                combined, label, fraction=frac, interval_sec=2.0
            ):
                session.upload(
                    identifier,
                    files=[str(path)],
                    metadata=file_meta,
                    verbose=True,
                )
    except Exception as exc:  # noqa: BLE001 — surface to TUI
        return UploadResult(ok=False, identifier=identifier, error=str(exc))

    url = f"https://archive.org/details/{identifier}"
    report(f"Uploaded: {url}", 1.0)
    return UploadResult(ok=True, identifier=identifier, item_url=url)
