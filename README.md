# dat-tracker

**dat-tracker** turns long, untrimmed live recordings into etree-style show packages: named FLAC tracks, info text, fingerprints, and tags — with as little manual waveform editing as possible.

It targets a common archive problem: **track splitting** (also called song boundary detection or cue-sheet generation) on continuous live transfers, especially **DAT → FLAC** dumps that arrive as one file per tape or set with **no embedded track markers**.

## The problem

Live transfers often arrive as one long FLAC per tape or set. Turning that into a publishable show means placing every track boundary, naming songs, keeping banter and tuning as their own tracks, marking segues, writing the info file, fingerprints, and tags — then repeating it for the next dump. Done carefully by hand in a waveform editor, that is hours per show and does not scale when someone drops a hundred untrimmed DATs.

Helpers exist, but they rarely finish the job:

- **Silence detection** (`ffmpeg silencedetect`, Audacity “Label Sounds”, browser splitters) — works poorly on live SBDs. Applause and room tone are not silence; thresholds that work in the studio find nothing on a gig tape, and thresholds that catch applause also fire inside songs.
- **Spectral / energy shifts** — closer to the right idea for live material (instrumentation vs crowd), and tools like [Audio File Splitter](https://github.com/luckymuck/Audio-File-Splitter) explore that — still usually ends in dragging markers on a waveform.
- **Fingerprinting** (ACRCloud, AudD, etc.) — can stamp known covers with timestamps; useless for material that is not in the database.

A realistic workflow with those tools on a two-hour set is: run detection, then spend a while fixing boundaries. Segues, quiet intros, and stage banter that runs into a count-in defeat a fully automatic silence pass.

(As an aside: search for “AI track splitting” and you mostly get **stem** splitters — vocals/drums/bass separation. That is a different task from chronological track marking on a continuous live recording.)

**dat-tracker** is built for the labor gap: automate the *tracking and packaging* pipeline, calibrate against already-excellent human-tracked shows, and treat remaining misses as rare exceptions — not as “open a waveform UI for every show.”

## What it does

1. **Ingest** continuous FLACs (and catalog them against known Archive.org items when you have them).
2. **Propose boundaries** with an ensemble of signals — not silence alone: energy/novelty, silence gaps, speech/banter islands (ASR), and (planned) music vs applause classifiers.
3. **Decide** track cuts, types (song / banter / tuning / intro / …), segues, and titles via an LLM that consumes that timeline plus show context and few-shot examples from calibration packages.
4. **Export** lossless cuts into etree-style names, Jon/etree-style `show.txt`, fingerprint files, and tags.
5. **Validate** against held-out, already-tracked packages so the tool does not overfit one dump or one taper’s quirks.
6. **Reuse** the same flow on other DAT (or similar continuous) dumps via config — Live Bluegrass is the first proving ground, not the only intended use.

## What “good” means here

Matching careful human tracking conventions, for example:

- Banter, tuning, and intros are **tracks**, not deleted dead air.
- Segues marked with `>` in titles/setlists.
- Filenames like `artistabbrevYYYY-MM-DD_t01.flac` or `_s1t01` / `_s2t01`.
- Bundle: FLAC + info `.txt` + fingerprint (`.ffp` / `fingerprint.ffp.txt`) + tags.
- Honest credit chains for transferer / tracker on Archive.org uploads.

Fully automatic release is the goal; confidence gates flag hard shows instead of requiring a waveform review workflow for every file.

## Status

Early development (**0.1.0**). Ingest, cataloging, calibration corpora, and proposal/scoring tooling are in progress; the full LLM decision loop and packaging path are the active work. See [CHANGELOG.md](CHANGELOG.md) and [PLAN.md](PLAN.md) for detail.

## Layout

| Path | Purpose |
|------|---------|
| `src/dat_tracker/` | Library code (catalog, proposals, calibration helpers, …) |
| `scripts/` | Download, score, and build utilities |
| `catalog/` | Show inventory and calibration manifests |
| `data/` | Local media (gitignored): raw dumps, ground truth, work, output |
| `docs/` | Extra notes |
| `tests/` | Pytest suite |

## Development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
# optional ASR extras
pip install -e ".[asr]"
pytest
```

System tools: `ffmpeg` (and typically `ffprobe`). Archive.org CLI extras come via the `internetarchive` dependency.

Agents and maintainers working in this repo should follow **[PLAN.md](PLAN.md)** and **[AGENTS.md](AGENTS.md)**.

## License

MIT — see `pyproject.toml`.
