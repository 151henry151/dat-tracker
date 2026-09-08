# bluegrass-dat-tracker

Track untrimmed live bluegrass DAT transfers (Dave W / Brian H collections) into etree-style FLAC sets and upload them to the Internet Archive.

Once this dump is calibrated and packaged, the same tooling is intended to be reusable on other DAT→FLAC dumps (see Phase 5 in PLAN.md).

## Start here

**Agents and humans:** follow **[PLAN.md](PLAN.md)**. That document is the source of truth for goals, conventions, phases, and the todo checklist.

## Quick links

- Dropbox (raw full-show FLACs, ~100 GB): see PLAN.md
- Ground truth on Archive.org: Dave Ward Collection / Brian H Collection (already tracked by Jon King)
- Reddit context: r/Bluegrass update thread linked in PLAN.md

## Layout

| Path | Purpose |
|------|---------|
| `data/raw/` | Dropbox dump |
| `data/ground_truth/` | Existing IA uploads for calibration |
| `data/work/` | Per-show working files |
| `data/out/` | Finished packages ready to upload |
| `catalog/` | Inventory of shows and status |
| `src/` | Pipeline code |
| `docs/` | Extra notes |

## Status

Phase 0 complete (scaffold at `0.1.0`). Next: Phase 1 — ingest Dropbox dump and build the show catalog. See **[PLAN.md](PLAN.md)**.

## Version

Current version: **0.1.0** — see [CHANGELOG.md](CHANGELOG.md).
