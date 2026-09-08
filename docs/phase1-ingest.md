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
- Dump filenames are mostly `YYMMDD_ABBREV…flac` or `YYYYMMDD_…flac` (not ISO dates in the name); multipart discs (`_1`/`_2`) coalesce to one catalog row
- J-card photo OCR is deferred; path/filename parsing covers the first inventory pass
- Calibration note: `prtr2002-08-02` is on IA but no matching raw FLAC was found in the zip listing

## Ground-truth boundaries

- Report Jon cut times (from track durations): `python scripts/report_ground_truth_boundaries.py jcb2002-08-02`
