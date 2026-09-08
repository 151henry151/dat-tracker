# dat-tracker

**dat-tracker** turns long, untrimmed live recordings into etree-style show packages: named FLAC tracks, info text, fingerprints, and tags — with as little manual waveform editing as possible.

It targets a common archive problem: **track splitting** (also called song boundary detection or cue-sheet generation) on continuous live transfers, especially **DAT → FLAC** dumps that arrive as one file per tape or set with **no embedded track markers**.

## The problem

Live transfers often arrive as one long FLAC per tape or set. Turning that into a publishable show means placing every track boundary, naming songs, keeping banter and tuning as their own tracks, marking segues, writing the info file, fingerprints, and tags — then repeating it for the next dump. Done carefully by hand in a waveform editor, that is hours per show and does not scale when someone drops a hundred untrimmed DATs.

Helpers exist, but they rarely finish the job on live soundboard / audience tapes:

- **Silence detection** — `ffmpeg silencedetect`, SoX `silence`, [mp3splt](https://mp3splt.sourceforge.net/) (`-s` silence mode), Audacity “Silence Finder” / “Label Sounds”, pydub `split_on_silence`, and countless “album splitter” GUIs. These work best on studio albums and podcasts with real dead air. Live SBDs keep applause and room tone in the mix; thresholds that work in the studio find nothing on a gig tape, and thresholds that catch applause also fire inside songs or on quiet bridges.
- **Spectral / energy / onset shifts** — closer to the right idea for live material (instrumentation vs crowd, or a hard attack into the next tune). Examples: RMS/novelty peak pickers, [Audio File Splitter](https://github.com/luckymuck/Audio-File-Splitter), [aubio](https://aubio.org/) (`aubioonset` / `aubiocut`), and MIR libraries such as [madmom](https://github.com/CPJKU/madmom) (onset / beat / downbeat models). They propose *many* plausible events; most are mid-song accents, not etree track starts. You still end up dragging markers.
- **Music structure analysis (research MSA)** — academic systems that segment songs into verse/chorus/sections or detect “boundaries” in pop recordings. Useful vocabulary and features; not trained on etree conventions (banter as its own track, `>` segues, applause glued to the previous song, etc.), and rarely shipped as a “split this DAT for Archive.org” product.
- **Fingerprinting / recognition** — ACRCloud, AudD, Shazam-class APIs stamp known studio (or heavily circulated) recordings with timestamps. Fine for a setlist of radio hits; useless for unreleased jams, alternate arrangements, and material that is not in the database.
- **Cue / CDDB / metadata-driven splitters** — [mp3splt](https://mp3splt.sourceforge.net/) with `.cue` / CDDB / Freedb, Flacon, shntool + cue, FFcuesplitter, foobar2000 playing an embedded cue. These **apply** known cut times; they do not **discover** them. Great once a human (or another tool) already tracked the show.
- **Fixed-interval / equal-length chops** — mp3splt time mode, audiobook “split every N minutes” tools. Handy for rough navigation; wrong model for songs of uneven length.
- **Manual waveform / DAW workflows** — Audacity label tracks, Reaper regions, Sound Forge, Izotope RX, etc., often paired with exporters (labels → cue). This is still how most careful live tracking gets done; the cost is human time.

A realistic workflow with the automatic helpers on a two-hour set is: run detection, then spend a while fixing boundaries. Segues, quiet intros, and stage banter that runs into a count-in defeat a fully automatic silence pass.

(As an aside: search for “AI track splitting” and you mostly get **stem** splitters — Demucs, UVR, Spleeter, and friends — vocals/drums/bass separation. That is a different task from chronological track marking on a continuous live recording.)

**dat-tracker** is built for the labor gap: automate the *tracking and packaging* pipeline, calibrate against already-excellent human-tracked shows, and treat remaining misses as rare exceptions — not as “open a waveform UI for every show.”

## Why this approach (and not only classical DSP or a laptop LLM)

**Classical detectors stay in the loop as navigation aids** — silence ends, energy novelty, speech/banter islands from ASR — because they are cheap and local. Alone they do not match careful human packaging: the hard cases are “where does the *next track* start for etree?” (often on banter or a count-in), not “where did RMS spike?”

**An audio-capable LLM listens to short clips around those candidates** (Google Gemini by default) and emits a structured tracking plan: keep / drop / nudge cuts, track types, titles, segues. Sparse clips keep API cost low (cents per show on paid Flash-class models) while still putting a model *in* the decision loop rather than only post-processing a transcript.

**Why not a fully local audio LLM on a typical laptop?** Models that actually *listen* (e.g. open audio-language models in the Qwen2-Audio class) need substantial GPU memory — often on the order of **8–16 GB VRAM** for comfortable inference — and are usually happiest on short clips anyway. A common mobile workstation GPU with ~4 GB VRAM is not a realistic drop-in for that job. Stacks people confuse with “local LLM tracking” — Whisper ASR plus a text-only Ollama/Llama chat model — never hear the music; they only reason about transcripts, which is the brittle path this project deliberately avoids for boundary placement.

**Why not “just train an LLM on Archive.org” yet?** In principle track splitting is a learnable perception problem, and IA has a huge supply of already-tracked packages. The practical recipe is close to what our Tier B calibration already uses: concatenate published tracks into a continuous file, hide the cuts, score recovery (synthetic re-split). Obstacles to a shippable specialist model today:

- **Supervision is packaging policy, not physics** — different trackers disagree on banter-as-track, applause tails, and segue cuts; a model learns *someone’s* conventions unless you curate carefully and hold out by taper/artist.
- **Synthetic joins ≠ raw DAT** — lossless concatenation is cleaner than real untrimmed tape (dropouts, tune-ups, tape flips). Models can overfit join artifacts and then fail on true continuous masters (our Tier A).
- **“Train an LLM” is the expensive end of the spectrum** — fine-tuning a large multimodal audio model needs data plumbing, money, and often limited fine-tune APIs. A smaller boundary detector (or distillation from Gemini judgments) may be the right long-term path; it is Phase 2b / research scale, not a substitute for a working sparse-listen loop while we calibrate.
- **Cost of iteration** — during development, paid cloud audio is cheap per show relative to engineering time; free-tier request caps are the usual friction, not dollar cost at Flash rates.

So the current design is intentional: **cheap local proposals → sparse cloud listening → calibrate hard against held-out human packages**, with room later for RAG over many show.txt files and optional trained specialists — without blocking Live Bluegrass packaging on a full custom training stack.

## What it does

1. **Ingest** continuous FLACs (and catalog them against known Archive.org items when you have them).
2. **Propose boundaries** with an ensemble of signals — not silence alone: energy/novelty, silence gaps, speech/banter islands (ASR), and (planned) music vs applause classifiers.
3. **Decide** track cuts, types (song / banter / tuning / intro / …), segues, and titles via an audio-native LLM that listens to sparse clips around candidates (plus show context / future few-shot from calibration packages).
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
cp .env.example .env   # set GEMINI_API_KEY for sparse audio tracking dry-runs
pytest
```

System tools: `ffmpeg` (and typically `ffprobe`). Archive.org CLI extras come via the `internetarchive` dependency.

Agents and maintainers working in this repo should follow **[PLAN.md](PLAN.md)** and **[AGENTS.md](AGENTS.md)**.

## License

MIT — see `pyproject.toml`.
