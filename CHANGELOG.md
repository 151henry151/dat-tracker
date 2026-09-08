# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- Rename project and Python package from `bluegrass-dat-tracker` / `bluegrass_dat_tracker` to `dat-tracker` / `dat_tracker`.

### Added

- Add resume-capable Dropbox zip download script targeting `data/raw/Live Bluegrass.zip`.
- Add Archive.org ground-truth download script for the 15 Dave Ward / Brian H calibration items.
- Add catalog builders for IA search docs, Dropbox zip paths, merge/status marking, and JSON/CSV writers.
- Add Jon-style `show.txt` formatter.
- Add `scripts/build_catalog.py` and Phase 1 ingest notes.

## [0.1.0] — 2026-09-08

### Added

- Add project scaffold with `pyproject.toml` at version 0.1.0.
- Add catalog JSON Schema and empty `shows` inventory under `catalog/`.
- Add `.gitignore` rules for `data/` media trees, common audio/archive extensions, and Python venvs.
