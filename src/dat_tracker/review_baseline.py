"""Snapshot and restore the LLM-delivered tracking plan for review reset."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from dat_tracker.review_plan import migrate_tracking_plan
from dat_tracker.tracking_plan import validate_tracking_plan

AS_DELIVERED_NAME = "tracking_plan_as_delivered.json"


def as_delivered_path(plan_path: Path) -> Path:
    """Sibling snapshot path next to the working tracking plan."""
    return Path(plan_path).parent / AS_DELIVERED_NAME


def write_as_delivered_snapshot(
    plan_path: Path,
    plan: dict[str, Any],
    *,
    overwrite: bool = False,
) -> Path:
    """Persist the LLM-delivered plan for later Reset-to-LLM.

    When ``overwrite`` is false, an existing snapshot is left untouched so
    review edits cannot replace the original suggestion.
    """
    dest = as_delivered_path(plan_path)
    if dest.is_file() and not overwrite:
        return dest
    payload = migrate_tracking_plan(copy.deepcopy(plan))
    # Snapshot should always look "pending" — approval is a review act.
    review = dict(payload.get("review") or {})
    review["status"] = "pending"
    review.pop("approved_at", None)
    review.pop("approved_by", None)
    payload["review"] = review
    dest.write_text(json.dumps(payload, indent=2) + "\n")
    return dest


def ensure_as_delivered_snapshot(
    plan_path: Path,
    plan: dict[str, Any],
) -> Path:
    """Write the snapshot once if missing (first open / legacy work dirs)."""
    return write_as_delivered_snapshot(plan_path, plan, overwrite=False)


def load_as_delivered(plan_path: Path) -> dict[str, Any] | None:
    path = as_delivered_path(plan_path)
    if not path.is_file():
        return None
    return migrate_tracking_plan(json.loads(path.read_text()))


def reset_plan_to_as_delivered(
    current: dict[str, Any],
    delivered: dict[str, Any],
    *,
    keep_package: bool = True,
) -> dict[str, Any]:
    """Replace cuts/tracks/notes with the LLM snapshot; optionally keep package."""
    current = migrate_tracking_plan(current)
    delivered = migrate_tracking_plan(copy.deepcopy(delivered))
    out = copy.deepcopy(delivered)
    if keep_package:
        out["package"] = copy.deepcopy(current.get("package") or {})
    review = dict(out.get("review") or {})
    review["status"] = "pending"
    review.pop("approved_at", None)
    review.pop("approved_by", None)
    out["review"] = review
    validate_tracking_plan(out)
    return out


def require_as_delivered(plan_path: Path) -> dict[str, Any]:
    """Load the snapshot or raise if the LLM baseline was never saved."""
    loaded = load_as_delivered(plan_path)
    if loaded is None:
        raise FileNotFoundError(
            f"No LLM baseline snapshot at {as_delivered_path(plan_path)}. "
            "Re-run tracking to create one, or open review once on an "
            "unedited plan so a snapshot can be created."
        )
    return loaded
