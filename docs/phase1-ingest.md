# Phase 1 notes

## Dropbox dump

- Shared zip: `Live Bluegrass.zip` → `data/raw/`
- Expected size: **107045111705** bytes
- Resume download: `./scripts/download_dropbox_zip.sh`
- Progress log: `logs/dropbox-download.log`

## Ground truth (Jon King IA uploads)

- Dest: `data/ground_truth/<identifier>/`
- Script: `./scripts/download_ground_truth.sh` (requires `.venv` + `internetarchive`)

## Catalog

- Schema: `catalog/schema.json`
- Build: `python scripts/build_catalog.py`
  - Always pulls Dave Ward / Brian H subject search from Archive.org
  - When the Dropbox zip is complete, also inventories FLAC paths via `unzip -l` and merges `todo` vs `already_uploaded`
- J-card photo OCR is deferred until the dump is extracted; path/filename parsing covers the first inventory pass
