# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Freeze Baseline A for the shipping-gates campaign: Tier B train mean F1 0.755 / min 0.533 / track |Δ|≤1 100% (pre-placement Gemini + early silence polish); document in `docs/baseline_a.md`.
- Harden early silence polish with RMS-rise / energy confirmation, short-range fallback, and speech/energy confirm channels; add `silence_ends_with_rms_rise`.
- Add train-only audio few-shot exemplars (`catalog/few_shot_train.json`) into the first Gemini listen pass.
- Add `preserve_well_spaced_prior_cuts` so Pro/refine cannot silently drop a well-spaced Flash mid-cut lattice.
- Add `--gap-fill` / `--gap-fill-max-seg-sec` flags to `scripts/run_tier_b_split.py` for guarded far-miss campaigns.

### Changed

- Require a confirmed nearby silence before `already_near` polish skip; ignore unconfirmed blips that trapped early cuts; widen confirmed early look-ahead to 55s.
- Gate gap-fill / Pro escalate on under-segmentation by track count so a single long jam in an already-dense lattice does not INSERT extra cuts.
- Soft-fail Gemini refine when JSON remains invalid after retries (keep the pre-refine plan) so long Tier A shows are not aborted mid-pipeline.
- Add an explicit REJECT hatch to the listen prompt: do not invent SNAP-forward boundaries when neither candidate nor forward_scrub shows a real transition.
- Densify mid-gap listen probes (60s step) on shows ≥1000s to reduce far-miss under-segmentation.
- Rewrite the first-listen prompt so ACCEPT/SNAP targets *next-track starts* (not song-end / mid-applause), add text few-shot placement examples, and document optional `forward_scrub` clips.
- Widen default first-listen half-window from 8s to 12s (forward scrub stays off by default after a train regression when enabled at +30s).
- After listen-center snap, polish clearly-early mid cuts forward onto the last dense silence end in a 12–45s look-ahead (`polish_early_cuts_to_silence_ends`).
- Strengthen refine prompt guidance to SNAP forward from applause/song-end onto next-track starts.
- Depersonalize maintainer-specific paths and credit defaults in PLAN/AGENTS/docs for public publication; default `--tracker` credit string is `dat-tracker`.
- Expand the README Status section with done / in-progress / calibration snapshot / roadmap.
- Ignore `data/calibration_tier_a/**` local extracts (absolute paths) the same way as other media under `data/`.
- Add a top-level MIT `LICENSE` file.

### Fixed

- Fix `merge_near_duplicate_cuts` dropping the mandatory show-start cut (0.0) instead of the spurious near-zero cut when a false opening banter/cheer boundary lands within the adaptive merge window; the old behavior let `ensure_endpoint_cuts` silently re-insert 0.0 afterward and restore the spurious cut. Raises Tier B train mean F1 @±15s from 0.644 to 0.661 and min F1 from 0.500 to 0.533 with no regressions on any train or holdout show.
- Fix `overlong_gap_probe_centers` snapping a gap-fill probe to the nearest *available* classical/energy/silence candidate even when that candidate sat far from the geometric target; add a `max_candidate_offset_sec` cap (default 90s) so a distant candidate no longer displaces an untethered target that is actually closer to where the missed boundary usually sits.
- Widen the `--gap-fill` INSERT listen clip from ±12s to ±45s so a probe built from a geometric estimate still covers the real transition when placement is off by tens of seconds.
- Tighten the gap-fill INSERT prompt to reject a dynamic shift inside one long song (solo, jam, tempo change) unless the model can name a concrete new-track marker (applause, spoken word, count-in, a new song starting from a stop); require `insert_decisions.reason` to name that marker.
- Probe every already-rejected classical candidate inside an overlong gap when there are only a few of them (`sparse_candidate_limit`, default 3), instead of only the one nearest a geometric midpoint — a real miss had the true boundary on the second-nearest candidate. Gaps with more candidates than that (a busy jam/solo song) keep the original single nearest-to-target probe so a dense false-candidate cluster does not get multiple chances to trigger a false INSERT.
- Lower Gemini `generate_content` temperature from 0.2 to 0.0 for both the first listen and refine/gap-fill passes. Re-running the same show with no code change had swung Tier B train F1 by up to 0.2-0.3 in either direction, making single-run comparisons unreliable; at temperature 0.0 one show reproduced an identical F1 across two independent fresh runs, though it does not fully eliminate variance (observed on another show).

### Changed

- Add explicit segue guidance to the first-listen prompt: a song flowing directly into the next with no real pause (count-in/first notes starting immediately, no applause/banter/silence) is not a track boundary — mark `segue_into_next` instead of splitting, per etree "Song A > Song B" convention. The prompt previously told the model to split "two clear song sections with ... count-in between" with no segue exception at all.

### Added

- Add `--gap-fill-max-seg-sec` to `scripts/track_show.py` so the gap-fill trigger threshold is configurable per show instead of fixed at 480s.

### Changed

- Restore tracking-plan endpoints (0 and duration) after the Gemini refine pass and again before writing the plan, so mid-cut-only refine responses do not drop the show start.
- Widen Gemini refine listen windows on longer shows (35s mid-length, 40s long) so typical ±15–40s placement errors fall inside the clip.
- Snap clearly-offset mid cuts onto the nearest speech/energy listen center within ±40s after Gemini listen.
- Skip forward speech-snap by default when the Gemini refine pass runs, so refine placements are not pulled into mid-song speech.
- Raise the long-show track-count budget from ~5.3 min/track to ~4 min/track and shorten speech-snap look-ahead on long shows.
- Rebalance the Gemini listen prompt toward etree banter/intro tracks and against under-segmentation; widen long-show refine windows to ±50s.
- Retry Gemini generate_content on transient HTTP/TLS transport errors (e.g. SSL bad-record-mac) in addition to 429/503.
- Skip refine_decisions entries with null or non-numeric from/to times instead of crashing the refine pass.
- Add an optional overlong-gap Gemini INSERT pass (`--gap-fill`, off by default) for clearly under-segmented plans.
- Retry Gemini refine/gap-fill when the model returns truncated or invalid JSON, matching the first-listen retry behavior.
- Auto-escalate under-segmented shows to Gemini Pro for gap-fill and refine; add a guarded early-cut→speech snap helper for near-miss polish experiments.
- Add Tier A helpers to align Jon packages inside extracted Live Bluegrass raws, write continuous extracts + known cuts, and score plans against them.
- Widen Gemini refine listen windows further on very long shows (≥4000s → ±60s) to cover typical Tier A near-miss placement errors.
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
- Add `scripts/run_tier_b_split.py` to batch-track a Tier B train or holdout split.
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
