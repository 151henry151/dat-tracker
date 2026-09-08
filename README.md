# dat-tracker

LLM-powered automatic tracking of untrimmed DAT→FLAC transfers into etree-style packages for the Internet Archive, calibrated so human waveform review is not required.

First proving ground: the Live Bluegrass Dave W / Brian H dump. The same tooling is intended for other DAT dumps of any genre (see Phase 5 in PLAN.md).

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

Phase 0 complete; Phase 1 ingest tooling in place (Dropbox + ground-truth downloads, catalog builders). Next: finish ingest, then Phase 2 LLM automatic tracking calibrated on Jon’s IA uploads. See **[PLAN.md](PLAN.md)**.

## Version

Current version: **0.1.0** — see [CHANGELOG.md](CHANGELOG.md).
