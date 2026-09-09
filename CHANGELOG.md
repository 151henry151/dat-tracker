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
- Expand the README helpers survey (silence, onset/MSA, fingerprinting, cue-driven, fixed-interval, DAW) and document why sparse cloud audio listening is preferred over laptop audio-LLMs or premature IA fine-tunes.
- Expand the README Usage section for Windows, macOS, and Linux (ffmpeg/ffprobe, venv, Gemini `.env`, `track_show`) and clarify the Development contributor flow.
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
- Add `track_show` orchestration and CLI (Whisper → sparse Gemini listen → optional package).
- Retry Gemini generate_content on transient 503 capacity errors with exponential backoff.
- Add optional Gemini refine pass and deterministic forward snap of cuts onto nearby speech onsets.
- Use overlong Whisper segment onsets as boundary anchors and densify probes when mid-show speech is sparse.
- Merge near-duplicate tracking cuts and add energy peaks as listen probes inside long speech-free gaps.
- Use longer adaptive cut spacing on long shows to reduce mid-song over-segmentation.
- Cap gap-probe listen centers on long shows while keeping speech anchors; use a longer speech-snap look-ahead; normalize plan endpoints to 0 and duration.
- Promote energy novelty peaks in medium speech gaps to listen anchors.
- Retry Gemini generate_content on 429 rate-limit errors with longer backoff.
- Retry Gemini listen when the model returns truncated or invalid JSON; raise max output tokens; prefer empty tracks arrays in the listen prompt.
- Materialize tracks from cuts_sec when Gemini returns an empty tracks array.
- Promote silence-end times in medium gaps to listen anchors.
- Snap clearly-late mid cuts (≥20 s) back onto a recent silence end after Gemini listen.
- Thin long-show cut lists to a duration-based max track count by dropping tightly sandwiched mid cuts.
- Add Tier B train/holdout plan scoring helpers and `scripts/score_tier_b_plans.py`.
- Lock numeric held-out calibration gates (Tier B mean F1 ≥ 0.85 @ ±15s; Tier A mean F1 ≥ 0.80) before Live Bluegrass batching.
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
