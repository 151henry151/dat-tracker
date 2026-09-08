# Calibration corpus notes

## Why

Tuning only on Jon King’s 15 Live Bluegrass IA packages will overfit that dump. We need held-out tracked DAT shows from the wider etree/LMA community, plus a path to learn from many already-tracked packages.

## Tiers

See PLAN.md Phase 2. Short version:

- **A:** Live Bluegrass raw + Jon packages (`data/ground_truth/`)
- **B:** Small external tracked DAT packages (`data/calibration/`) + synthetic re-split
- **C:** Broader IA DAT tracked index for RAG / later training

## Cate Crowe + Jon King on IA

As of 2026-09-08, IA search for Cate Crowe transfer + Jon King tracking returns **the same 15** Dave Ward / Brian H items (~10 GB). There is not a second Cate/Jon bluegrass set to download for diversity. Jon’s other uploads are mostly modern audience/matrix tapers (different task).

## Seed ideas for Tier B (curate before download)

Search themes (cap size, prefer complete FLAC + info txt + ffp):

- etree or taperssection
- bluegrass / newgrass / adjacent jamgrass artists
- lineage or source mentions DAT
- item size roughly 80–450 MB for a first batch

Example identifiers surfaced by size-capped search (quality not yet vetted—check info files manually):

- `del2001-04-27.flac16` (~94 MB)
- `sbb2001-04-27.flac16` (~139 MB, Sam Bush)
- `los1999-06-27.taperchadrecordings` (~167 MB)
- `ymsb2007-02-24.flac16` (~177 MB)
- `jcb2004-04-16.sbd.kp.flac16` (~251 MB)

## First curated Tier B batch

Manifest: `catalog/calibration_tier_b.json` (10 shows, ~1.3 GB FLAC, train/holdout split).

```bash
./scripts/download_calibration_tier_b.sh
python scripts/build_synthetic_resplit.py
```

Synthetic continuous files and `known_cuts.json` land under `data/calibration/<id>/`.

## Synthetic re-split

For Tier B/C without continuous masters: concatenate track FLACs in order → one continuous file; store known cut times from durations; score the tracker against those cuts. Use as held-out metric alongside true Tier A raws.
