---
# npppppppppppttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttt[]9ZAhjjame: Bluegrass DAT Tracking
overview: Download the full ~100GB Live Bluegrass Dropbox dump, build a human-in-the-loop AI tracking pipeline calibrated against Jon King’s already-uploaded Archive.org shows, then track and package every remaining show to etree/LMA standards for upload under your Archive.org account.
todos:
  - id: scaffold
    content: Create bluegrass-dat-tracker project with semver, changelog, data dirs, catalog schema
    status: pending
  - id: download-dropbox
    content: Download full ~100GB Live Bluegrass Dropbox dump into data/raw with resume
    status: pending
  - id: ground-truth
    content: Download all Dave Ward / Brian H IA items; mark catalog already_uploaded vs todo
    status: pending
  - id: boundary-engine
    content: Implement ensemble boundary proposer + compare cuts to Jon ground-truth FLACs
    status: pending
  - id: review-ui
    content: Build local waveform review UI for nudge/merge/split/label + segue marks
    status: pending
  - id: package-export
    content: Export etree-named FLACs, Jon-style txt, ffp, tags; calibrate until ground-truth match
    status: pending
  - id: batch-upload
    content: Track remaining shows; upload new items via ia CLI to etree or taperssection with correct credits
    status: pending
isProject: false
---

# Bluegrass DAT track-and-upload workflow

## Context we already verified

- **Dropbox** ([Live Bluegrass](https://www.dropbox.com/scl/fo/lwcwu3y8qwktcdmcwt5b0/AFV4nzvqJ66AZ1vSMjs85vE?rlkey=62qci0un4hk40q9s0zu7r5gdg&dl=0)): ~**100 GB** zip; folders `Dave W Flacs`, `Brian H Flacs` (+ Wave 2/3), `Read Me_090726.txt`. Transfers are **untrimmed continuous FLACs with no track markers** (Cate Crowe: `DAT > Sony PCM-2600 > ESI U24XL > Audacity > FLAC`).
- **Already on Archive.org** (ground truth): [Dave Ward Collection](https://archive.org/search?query=subject%3A%22Dave+Ward+Collection%22) (5) + [Brian H Collection](https://archive.org/search?query=subject%3A%22Brian+H+Collection%22) (10) ≈ **15 items / ~8 GB** tracked FLACs. Tracker/uploader: **Jon King**; transferer: **Cate Crowe**.
- **Their tracking conventions** (match these exactly):
  - Filenames: `{abbrev}{yyyy-mm-dd}_t01.flac` or `_s1t01` / `_s2t01` for multi-set (no spaces).
  - Banter / tuning / intros / encore breaks are **their own tracks**, not deleted.
  - Segues marked `>` in titles/setlist.
  - Bundle: show `.txt` + `fingerprint.ffp.txt` (xACT-style FFP) + FLAC tags.
  - IA: band **etree** collection when it exists, else **`taperssection`**; subject tags include `Dave Ward Collection` / `Brian H Collection`; credit transferer + tracker in description/txt.

```mermaid
flowchart LR
  dropbox[Dropbox ~100GB] --> local[Local raw FLACs]
  local --> propose[AI propose boundaries]
  propose --> review[Human waveform review]
  review --> package[Name tag txt ffp]
  package --> validate[Diff vs Jon IA uploads]
  validate --> upload[ia upload etree or taperssection]
```

## Decisions locked in

- Download **entire** Dropbox dump (fits locally).
- Track **all** shows; do **not** wait on coordination first.
- Treat Jon’s uploads as **calibration targets**: if our splits/names/metadata match those shows, proceed to package the rest for your Archive.org account.

## Phase 0 — Project skeleton

New project (not inside the Lenovo backup dump), e.g. `~/src/bluegrass-dat-tracker` (or similar), with semver + Keep a Changelog from day one.

Layout sketch:

- `data/raw/` — Dropbox dump
- `data/ground_truth/` — downloaded Jon IA items (audio + txt + ffp)
- `data/work/` — per-show working dirs
- `data/out/` — finished etree-style packages ready to upload
- `catalog/` — inventory CSV/JSON (path, artist, date, venue, collection, status, IA id if any)
- `src/` — pipeline code
- `CHANGELOG.md`, `VERSION` / `pyproject.toml`

## Phase 1 — Ingest and inventory

1. Download full shared folder (Dropbox desktop “Copy to Dropbox”, or `rclone`/`curl` zip with resume; verify ~100 GB and checksum where possible).
2. Parse J-card photos + folder/file names into a **catalog** of candidate shows.
3. Cross-reference catalog against IA search (`subject:"Dave Ward Collection"` / `Brian H Collection` and artist+date) → mark rows `already_uploaded` vs `todo`.
4. Download all already-uploaded items into `data/ground_truth/` (FLACs + `.txt` + `fingerprint.ffp.txt`) for offline comparison.

## Phase 2 — AI-assisted tracking (human-in-the-loop)

**Goal:** Propose split points; a human (you / Jay / Chris) confirms on a waveform. Fully automatic release is not the bar — matching Jon’s style is.

Pipeline per raw full-show FLAC:

1. **Decode once** to a working WAV/PCM cache (or stream via ffmpeg) for analysis.
2. **Boundary proposal** (ensemble, not silence-only):
   - Energy / onset envelope + silence gaps (pydub/librosa/ffmpeg `silencedetect`).
   - Music vs non-music classifier (e.g. YAMNet-style approach as in [XTRACK](https://github.com/FlorianColombo/xtrack)) for applause / speech / music — critical because bluegrass often has **short** gaps and **long banter** that must stay as tracks.
   - Optional: chroma/novelty for song-to-song changes when applause is continuous.
3. **Review UI** (minimal, local): waveform + proposed cut markers; nudge/merge/split; label track type (song / banter / tuning / intro / encore break); mark segues.
4. **Export cuts** losslessly (`flac`/`sox`/`ffmpeg` sample-accurate) into etree filenames.
5. **Setlist assist**: optional ASR on banter + music fingerprint / LLM title guess from snippets — always human-editable; ground-truth shows teach expected title style.
6. Emit **show.txt** (copy Jon’s template: artist, date, venue, source, transfer, “Tracked & Uploaded by: …”, setlist, notes about Dave/Brian collections) + **fingerprint.ffp.txt** + Vorbis tags on each FLAC.

Calibration loop on the ~15 ground-truth shows:

- Run proposal → compare cut times to Jon’s track boundaries (align via cross-correlation / duration matching).
- Metrics: boundary F1 within ±N ms, track-count match, title similarity.
- Tune thresholds / post-rules (e.g. keep short speech islands as Banter; don’t merge across clear applause) until agreement is strong on a held-out subset of those shows.
- Only then batch-process the rest with the same review discipline.

## Phase 3 — Package and upload standards

For each finished show:

- Identifier / dir: etree style (`del2005-05-29`, `hotrize1996-06-09`, source suffix if needed e.g. `.sbd`).
- Choose collection: existing LMA band collection if present and band policy allows; otherwise `taperssection` (as Jon did for Hot Rize, Doc Watson, OCMS, etc.).
- Metadata fields: title, creator, date, venue, coverage, source, lineage, taper, transferer, subject tags including collection name.
- Upload via Archive.org account (`ia` CLI or web LMA uploader). Credit chain must remain honest: Cate Crowe transfer; you as tracker/uploader; note source collection.

Do **not** re-upload the calibration shows as competing items if they already exist; use them only for validation. New uploads are for catalog rows still missing from IA (and any clearly distinct sources, e.g. SBD vs Matrix already separated).

## Phase 4 — Present results

Once ground-truth match is solid and a first batch of new shows is packaged:

- Draft (for you to post) a Reddit reply / email to OP summarizing method, validation against Jon’s uploads, and links to your new IA items — offer the workflow/tooling if useful.
- Keep a public checklist in the catalog of done vs remaining.

## Suggested implementation order (after you approve this plan)

1. Scaffold project + changelog/version.
2. Start full Dropbox download; while it runs, pull ground-truth IA items + write catalog schema and Jon-template txt generator.
3. Build boundary proposer + offline diff against one known show (e.g. `jcb2002-08-02`).
4. Add review UI; calibrate on all ground-truth shows.
5. Process remaining shows in priority waves; upload when packages pass checklist.

## Risks / notes

- **100 GB** download may take hours; use resume-capable tooling.
- Some bands lack LMA permission → `taperssection` path is intentional, not a failure.
- Live bluegrass banter density means silence-only splitters will fail calibration; classifier + human review is required.
- OP Read Me still welcomes tracking help; publishing after validation reduces collision risk without blocking work.
