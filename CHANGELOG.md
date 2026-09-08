# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- Rename project and Python package from `bluegrass-dat-tracker` / `bluegrass_dat_tracker` to `dat-tracker` / `dat_tracker`.
- Change Phase 2 from human-in-the-loop waveform review to LLM-powered automatic tracking with calibration-gated release and exceptional-only human spot-checks.
- Parse Live Bluegrass dump filenames with leading `YYMMDD` / `YYYYMMDD` dates and known artist abbrevs into catalog rows; coalesce multipart raw FLACs.
- Expand calibration strategy to multi-corpus tiers (Live Bluegrass pairs, external tracked DAT packages, broader RAG/training corpus) so evaluation does not overfit one dump.
- Broaden track FLAC ordering to compact `…tNN…` and `dNtMM` etree filename styles used by external packages.
- Rewrite README as a public-facing description of track splitting, the product goal, and how dat-tracker approaches it.
- Reframe the README problem statement around manual tracking labor; mention stem-splitter search confusion only as a brief aside.
- Lock Phase 2 on an audio-native LLM-in-the-loop tracker (Gemini preferred); classical/ASR features are optional aids, not a text-only substitute for listening.
- Prefer sparse Gemini listening on short clips around candidate cuts (Flash by default) to limit audio token cost.

### Added

- Add speech-island filtering, merge, and speech-prioritized boundary proposals that snap to energy and sparsely fill long song gaps.
- Add tracking-plan JSON Schema plus heuristic draft builder and Del holdout dry-run script.
- Add sparse Gemini listening helpers (clip windows, `.env` loader) and Del dry-run against the tracking-plan schema.
- Add `.env.example` documenting `GEMINI_API_KEY` and default Flash model.
- Add mid-gap probe centers and ACCEPT/REJECT/SNAP listening prompt so Gemini can drop false proposals and scrub long spans.
- Add lossless FLAC track export from a tracking-plan JSON.
- Add show.txt and fingerprint.ffp.txt packaging from a tracking plan (FLAC STREAMINFO MD5, no metaflac).
- Add resume-capable Dropbox zip download script targeting `data/raw/Live Bluegrass.zip`.
- Add Archive.org ground-truth download script for the 15 Dave Ward / Brian H calibration items.
- Add catalog builders for IA search docs, Dropbox zip paths, merge/status marking, and JSON/CSV writers.
- Add Jon-style `show.txt` formatter.
- Add `scripts/build_catalog.py` and Phase 1 ingest notes.
- Add ground-truth boundary cut extraction and F1 comparison helpers plus `scripts/report_ground_truth_boundaries.py`.
- Add Tier B external calibration manifest, download script, and synthetic re-split helpers.
- Document the perception → LLM decision → archive-learning stack for automatic tracking.
- Add RMS energy / novelty boundary proposals and a Tier B scoring script.
- Add candidate fusion across silence/energy/speech sources and faster-whisper speech-edge proposals.

## [0.1.0] — 2026-09-08

### Added

- Add project scaffold with `pyproject.toml` at version 0.1.0.
- Add catalog JSON Schema and empty `shows` inventory under `catalog/`.
- Add `.gitignore` rules for `data/` media trees, common audio/archive extensions, and Python venvs.
