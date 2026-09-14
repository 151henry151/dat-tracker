# Contributing

Thanks for taking an interest in **dat-tracker**. Contributions of code, docs, bug reports, and ideas are welcome.

## Before you dive in

Read **[PLAN.md](PLAN.md)** for where the project is, what is locked, and what still needs to happen before dump-wide shipping. That file is the source of truth for product decisions; older chat notes and archived docs under [`docs/`](docs/README.md) are historical.

Also skim **[README.md](README.md)** (try-out and background) and **[AGENTS.md](AGENTS.md)** if you are working in an agent-assisted checkout.

## How to contribute

1. **Open an issue** for bugs, ideas, or questions — or email **151henry151@gmail.com** if you prefer.
2. To send code: **fork** the repository, create a branch, and open a **pull request** against `main`.
3. Keep PRs focused. Prefer small, reviewable changes over large mixed dumps.

You do not need to ask permission before filing an issue or a draft PR. If you are unsure whether an idea fits, an issue first is fine.

## Development practice (TDD)

Behavior changes (features, bug fixes, refactors that change behavior) should follow **red → green → refactor**:

1. **Red** — Add or extend a test that fails for the right reason.
2. **Green** — Write the minimal production code to make it pass.
3. **Refactor** — Clean up only while tests stay green.

Exceptions: pure chores with no behavior change (formatting, renames, changelog-only, docs-only), or tooling where a harness does not exist yet — note that in the PR.

Run the suite from a venv with extras:

```bash
pip install -e ".[asr,review,dev]"
pytest
```

## Changelog

Every PR that changes user-facing or library behavior (or docs worth announcing) should update **[CHANGELOG.md](CHANGELOG.md)** under **`## [Unreleased]`**.

- Use the imperative (“Add…”, “Change…”, “Fix…”).
- Describe the code/docs change; do not claim “fixed issue #N” as the changelog body — link the issue in the PR instead.
- Group under Added / Changed / Fixed / Removed as appropriate ([Keep a Changelog](https://keepachangelog.com/)).

Do not bump the version unless the maintainer asks; we stay on **0.1.x** until calibration gates in PLAN.md pass.

## Pull request tips

- Imperative commit messages (same style as the changelog).
- Include how you tested (`pytest`, a manual `dat-review` path, etc.).
- Do not commit large media under `data/`, FLACs, or secrets (`.env`, API keys).
- Do not re-upload Archive.org items marked `already_uploaded` in the catalog — those are for calibration only.

## Questions and feedback

Bugs, confusion in the docs, packaging problems, or “what if we…” suggestions: open a [GitHub issue](https://github.com/151henry151/dat-tracker/issues) or email **151henry151@gmail.com**.
