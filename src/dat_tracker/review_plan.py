"""Review status, Accept-all, and packaging gate for tracking plans."""

from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from dat_tracker.tracking_plan import validate_tracking_plan

ApproveMethod = Literal["accept_all", "edited"]


class ReviewNotApprovedError(RuntimeError):
    """Raised when packaging is attempted without an approved review."""


def empty_package_fields() -> dict[str, Any]:
    return {
        "artist": None,
        "date": None,
        "venue": None,
        "city": None,
        "state": None,
        "source": None,
        "transfer": None,
        "transferer": None,
        "tracker": None,
        "collection_subjects": [],
        "set_label": None,
        "notes": None,
    }


def pending_review() -> dict[str, Any]:
    return {
        "status": "pending",
        "approved_at": None,
        "approved_by": None,
        "method": None,
    }


def migrate_tracking_plan(plan: dict[str, Any]) -> dict[str, Any]:
    """Upgrade a 1.0.0 (or incomplete) plan to 1.1.0 with package + review."""
    out = copy.deepcopy(plan)
    version = str(out.get("schema_version") or "1.0.0")
    if version not in {"1.0.0", "1.1.0"}:
        version = "1.0.0"
    out["schema_version"] = "1.1.0"

    package = dict(empty_package_fields())
    existing_pkg = out.get("package")
    if isinstance(existing_pkg, dict):
        for key in package:
            if key in existing_pkg:
                package[key] = existing_pkg[key]
    out["package"] = package

    existing_review = out.get("review")
    if isinstance(existing_review, dict) and existing_review.get("status") in {
        "pending",
        "approved",
        "rejected",
    }:
        review = {
            "status": existing_review["status"],
            "approved_at": existing_review.get("approved_at"),
            "approved_by": existing_review.get("approved_by"),
            "method": existing_review.get("method"),
        }
    else:
        review = pending_review()
    out["review"] = review
    return out


def review_status(plan: dict[str, Any]) -> str:
    review = plan.get("review")
    if isinstance(review, dict) and review.get("status"):
        return str(review["status"])
    return "pending"


def is_review_approved(plan: dict[str, Any]) -> bool:
    return review_status(plan) == "approved"


def approve_plan(
    plan: dict[str, Any],
    *,
    method: ApproveMethod,
    approved_by: str | None = None,
) -> dict[str, Any]:
    """Mark plan approved; does not alter cuts_sec."""
    out = migrate_tracking_plan(plan)
    out["review"] = {
        "status": "approved",
        "approved_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "approved_by": approved_by,
        "method": method,
    }
    out["needs_review"] = False
    validate_tracking_plan(out)
    return out


def assert_review_approved_for_package(
    plan: dict[str, Any],
    *,
    force_unreviewed: bool = False,
) -> None:
    """Refuse packaging unless review is approved (or force escape hatch)."""
    if force_unreviewed:
        return
    if is_review_approved(plan):
        return
    status = review_status(plan)
    raise ReviewNotApprovedError(
        f"Tracking plan review status is {status!r}; approve with dat-review "
        "(or --accept-all) before packaging, or pass --force-unreviewed."
    )


def accept_all_plan_file(
    plan_path: Path,
    *,
    approved_by: str | None = None,
) -> dict[str, Any]:
    """Load plan, Accept-all approve, write back, return approved plan."""
    raw = json.loads(plan_path.read_text())
    approved = approve_plan(raw, method="accept_all", approved_by=approved_by)
    plan_path.write_text(json.dumps(approved, indent=2) + "\n")
    return approved


def package_fields_from_plan(
    plan: dict[str, Any],
    *,
    defaults: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Merge plan.package with CLI/catalog defaults (plan wins when set)."""
    defaults = defaults or {}
    pkg = plan.get("package") if isinstance(plan.get("package"), dict) else {}
    keys = (
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
    )
    out: dict[str, Any] = {}
    for key in keys:
        val = pkg.get(key)
        if val is None or val == "":
            val = defaults.get(key)
        out[key] = val
    subjects = pkg.get("collection_subjects")
    if not subjects:
        subjects = defaults.get("collection_subjects") or []
    out["collection_subjects"] = list(subjects)
    return out
