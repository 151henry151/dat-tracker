"""CLI entry point for `dat-review` — picker by default, optional --plan/--show."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from dat_tracker.review_discover import (
    discover_reviewable_shows,
    resolve_show_for_review,
)
from dat_tracker.review_hydrate import (
    hydrate_plan_from_companions,
    hydrate_plan_from_notes,
)
from dat_tracker.review_package_polish import polish_package_metadata
from dat_tracker.review_plan import accept_all_plan_file, migrate_tracking_plan

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _project_root() -> Path:
    """Prefer repo root when running from a checkout; else cwd."""
    if (_REPO_ROOT / "catalog").is_dir() and (_REPO_ROOT / "data").exists():
        return _REPO_ROOT
    return Path.cwd()


def prepare_plan(
    raw: dict[str, Any],
    *,
    project_root: Path,
    artist: str | None = None,
    date: str | None = None,
    tracker: str | None = None,
    venue: str | None = None,
    city: str | None = None,
    state: str | None = None,
) -> dict[str, Any]:
    plan = migrate_tracking_plan(raw)
    plan = hydrate_plan_from_notes(plan)
    plan = hydrate_plan_from_companions(
        plan,
        project_root=project_root,
        artist=artist,
        date=date,
        tracker=tracker,
        venue=venue,
        city=city,
        state=state,
    )
    plan = polish_package_metadata(plan, project_root=project_root, use_llm=True)
    return plan


def _resolve_source(
    *,
    plan: dict[str, Any],
    explicit: Path | None,
    project_root: Path,
    fallback: Path | None,
) -> Path | None:
    if explicit is not None:
        return explicit
    if fallback is not None and fallback.is_file():
        return fallback
    if plan.get("source_path"):
        candidate = Path(str(plan["source_path"]))
        if candidate.is_file():
            return candidate
        alt = project_root / candidate
        if alt.is_file():
            return alt
    return fallback


def run_interactive_review(
    *,
    plan_path: Path,
    source_audio: Path | None,
    project_root: Path,
    approved_by: str | None = None,
    artist: str | None = None,
    date: str | None = None,
    tracker: str | None = None,
    venue: str | None = None,
    city: str | None = None,
    state: str | None = None,
) -> int:
    try:
        from dat_tracker.tui_review.app import run_review_app
    except ImportError as exc:
        print(
            "Interactive review requires the optional [review] extras "
            f"(pip install -e '.[review]'): {exc}",
            file=sys.stderr,
        )
        print("Or use --accept-all for the headless fast path.", file=sys.stderr)
        return 2

    plan = prepare_plan(
        json.loads(plan_path.read_text()),
        project_root=project_root,
        artist=artist,
        date=date,
        tracker=tracker or approved_by,
        venue=venue,
        city=city,
        state=state,
    )
    source = _resolve_source(
        plan=plan,
        explicit=source_audio,
        project_root=project_root,
        fallback=None,
    )
    print("Opening review TUI…", file=sys.stderr)
    return int(
        run_review_app(
            plan_path=plan_path,
            plan=plan,
            source_audio=source,
            approved_by=approved_by,
            rehydrate=False,
        )
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Review tracking plans. With no arguments, ask for a FLAC dump "
            "directory, list shows, track if needed, then review. "
            "Pass a show id, --plan, or --work-plans to skip the dump prompt."
        )
    )
    parser.add_argument(
        "show",
        nargs="?",
        default=None,
        help="Show id under data/work (skips picker)",
    )
    parser.add_argument(
        "--plan",
        type=Path,
        default=None,
        help="Path to tracking_plan_gemini.json (power-user / scripting)",
    )
    parser.add_argument(
        "--show",
        dest="show_opt",
        default=None,
        help="Show id under data/work (same as positional SHOW)",
    )
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=None,
        help="Work root containing per-show dirs (default: <root>/data/work)",
    )
    parser.add_argument(
        "--dump-root",
        type=Path,
        default=None,
        help="Skip the dump prompt and list FLACs under this directory",
    )
    parser.add_argument(
        "--work-plans",
        action="store_true",
        help="Skip dump prompt; list existing data/work tracking plans only",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Project root (default: package checkout or cwd)",
    )
    parser.add_argument(
        "--accept-all",
        action="store_true",
        help="Approve the plan without opening the TUI (fast path)",
    )
    parser.add_argument(
        "--approved-by",
        default=None,
        help="Optional reviewer identity stored on the plan",
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=None,
        help="Continuous FLAC override (defaults from plan / calibration)",
    )
    parser.add_argument("--artist", default=None)
    parser.add_argument("--date", default=None, help="YYYY-MM-DD")
    parser.add_argument("--tracker", default=None)
    parser.add_argument("--venue", default=None)
    parser.add_argument("--city", default=None)
    parser.add_argument("--state", default=None)
    parser.add_argument(
        "--setup-defaults",
        action="store_true",
        help="Open the tracker-name defaults form and exit",
    )
    parser.add_argument(
        "--skip-defaults-prompt",
        action="store_true",
        help="Do not offer first-run defaults setup before the show picker",
    )
    args = parser.parse_args(argv)

    project_root = Path(args.root) if args.root else _project_root()
    work_dir = args.work_dir
    show_id = args.show_opt or args.show

    if args.setup_defaults:
        try:
            from dat_tracker.tui_review.defaults_setup import run_defaults_setup
        except ImportError as exc:
            print(
                "Defaults setup requires [review] extras "
                f"(pip install -e '.[review]'): {exc}",
                file=sys.stderr,
            )
            return 2
        saved = run_defaults_setup(project_root=project_root)
        print("Saved operator defaults." if saved else "Skipped.", file=sys.stderr)
        return 0 if saved else 1

    # Defaults (when missing) are prompted inside ReviewSessionApp so the
    # operator never leaves the TUI between setup and dump/review.
    prompt_defaults = not args.skip_defaults_prompt

    plan_path: Path | None = args.plan
    source_from_show: Path | None = None

    if plan_path is None:
        if show_id:
            found = resolve_show_for_review(
                show_id, project_root=project_root, work_dir=work_dir
            )
            if found is None:
                print(
                    f"No tracking plan found for show {show_id!r} under "
                    f"{work_dir or project_root / 'data' / 'work'}",
                    file=sys.stderr,
                )
                return 1
            plan_path = found.plan_path
            source_from_show = found.source_path
        elif args.accept_all:
            print(
                "--accept-all requires a show id or --plan PATH",
                file=sys.stderr,
            )
            return 2
        else:
            # Interactive: dump-first (default), or work-plans / --dump-root.
            try:
                from dat_tracker.tui_review.session import run_review_session
            except ImportError as exc:
                print(
                    "Show picker requires the optional [review] extras "
                    f"(pip install -e '.[review]'): {exc}",
                    file=sys.stderr,
                )
                print(
                    "Or pass a show id: dat-review <show-id>",
                    file=sys.stderr,
                )
                return 2
            if args.work_plans:
                shows = discover_reviewable_shows(
                    project_root=project_root, work_dir=work_dir
                )
                return run_review_session(
                    shows=shows,
                    project_root=project_root,
                    approved_by=args.approved_by,
                    artist=args.artist,
                    date=args.date,
                    tracker=args.tracker,
                    venue=args.venue,
                    city=args.city,
                    state=args.state,
                    source_override=args.source,
                    dump_first=False,
                    work_dir=work_dir,
                    prompt_defaults=prompt_defaults,
                )
            if args.dump_root is not None:
                from dat_tracker.dump_discover import discover_dump_shows

                dump = Path(args.dump_root).expanduser()
                if not dump.is_absolute():
                    dump = (project_root / dump).resolve()
                if not dump.is_dir():
                    print(f"Dump root is not a directory: {dump}", file=sys.stderr)
                    return 1
                shows = discover_dump_shows(
                    dump, project_root=project_root, work_dir=work_dir
                )
                return run_review_session(
                    shows=shows,
                    project_root=project_root,
                    approved_by=args.approved_by,
                    artist=args.artist,
                    date=args.date,
                    tracker=args.tracker,
                    venue=args.venue,
                    city=args.city,
                    state=args.state,
                    source_override=args.source,
                    dump_first=False,
                    work_dir=work_dir,
                    dump_root=dump,
                    prompt_defaults=prompt_defaults,
                )
            return run_review_session(
                shows=[],
                project_root=project_root,
                approved_by=args.approved_by,
                artist=args.artist,
                date=args.date,
                tracker=args.tracker,
                venue=args.venue,
                city=args.city,
                state=args.state,
                source_override=args.source,
                dump_first=True,
                initial_dump_root=None,
                work_dir=work_dir,
                prompt_defaults=prompt_defaults,
            )

    assert plan_path is not None
    if not plan_path.is_file():
        print(f"Plan not found: {plan_path}", file=sys.stderr)
        return 1

    if args.accept_all:
        prepared = prepare_plan(
            json.loads(plan_path.read_text()),
            project_root=project_root,
            artist=args.artist,
            date=args.date,
            tracker=args.tracker or args.approved_by,
            venue=args.venue,
            city=args.city,
            state=args.state,
        )
        plan_path.write_text(json.dumps(prepared, indent=2) + "\n")
        approved = accept_all_plan_file(plan_path, approved_by=args.approved_by)
        print(
            f"Approved {plan_path} method=accept_all "
            f"cuts={len(approved.get('cuts_sec') or [])}",
            file=sys.stderr,
        )
        return 0

    source = args.source or source_from_show
    if source is None:
        # Last chance from prepared plan paths after hydrate.
        raw = json.loads(plan_path.read_text())
        source = _resolve_source(
            plan=raw,
            explicit=None,
            project_root=project_root,
            fallback=source_from_show,
        )

    return run_interactive_review(
        plan_path=plan_path,
        source_audio=source,
        project_root=project_root,
        approved_by=args.approved_by,
        artist=args.artist,
        date=args.date,
        tracker=args.tracker,
        venue=args.venue,
        city=args.city,
        state=args.state,
    )


if __name__ == "__main__":
    raise SystemExit(main())
