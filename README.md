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

Fully automatic *proposal* is the goal; packaging still goes through a required review gate (`dat-review`) with a one-key **Accept-all** fast path when the plan looks good.

## Status

Early development (**0.1.0**). Version stays at 0.1.0 until Live Bluegrass packaging passes the locked calibration gates in [PLAN.md](PLAN.md). Do **not** treat the dump’s remaining `todo` FLACs as ready to batch yet — calibration quality is still below the bar.

### Done

- Project scaffold (semver, changelog, catalog schema, MIT license).
- Live Bluegrass Dropbox ingest helpers, IA ground-truth download path, and catalog merge (`already_uploaded` vs `todo`).
- Tier B external calibration corpus + synthetic re-split harness (train/holdout manifests and scorers).
- Tier A helpers to align Jon packages inside extracted raws and score plans against known cuts.
- Classical/ASR proposal stack (silence, energy, speech islands) feeding sparse Gemini listening.
- End-to-end `scripts/track_show.py`: Whisper → Gemini Flash listen → optional refine / gap-fill / Pro escalate → tracking-plan JSON → **review gate** → optional etree package export.
- Cross-platform Textual review TUI (`dat-review`): run with no args to pick a show from `data/work` (picker stays in the TUI through prepare into review), or `dat-review <show-id>`; waveform overview/detail, cut edit, track/package metadata, playback, Accept-all / Save&approve; packaging refuses unapproved plans unless `--force-unreviewed`.
- Hardening from calibration loops: endpoint restoration, refine windows, snaps, JSON/transport retries, near-zero merge fix, sparse gap-fill probes, temperature 0.0, segue guidance in the listen prompt.

### In progress

- Raising **boundary F1** and track-count agreement to the shipping gates (still failing on held-out Tier B and Tier A).
- Making gap-fill reliable on hard under-segmented shows (e.g. some YMSB Tier B cases) without mid-song false inserts.
- Reducing run-to-run variance on ambiguous shows even at temperature 0.0.
- Near-miss placement polish (many cuts land within ~15–60 s of truth but miss the ±15 s gate).
- Guarding Pro escalate so it cannot collapse a reasonable mid-cut lattice (seen on some Tier A runs).

### Latest calibration snapshot (approximate)

Tune on **train**, not holdout. Numbers move as plans are regenerated.

**Baseline A** (frozen for the shipping-gates campaign — see [docs/baseline_a.md](docs/baseline_a.md)): Tier B train mean F1 **0.755**, min **0.533**, track \|Δ\|≤1 **100%**. Plans under `data/work/.baseline_a/`.

| Set | mean F1 @ ±15 s | Notes |
|-----|-----------------|--------|
| Tier B train (best merged) | **0.804** | min **0.714**; track \|Δ\|≤1 **60%** (los over-seg). Escalate density gate + soft polish landed; fresh Gemini runs still flip lattices |
| Tier B holdout (fresh) | **0.596** | Gate: mean ≥ **0.85**, min ≥ **0.70** — **FAIL** (ymsb ~0.31, jcb ~0.42) |
| Tier A (3 shows) | ~0.34 | Gate: mean ≥ **0.80** — **FAIL**; Pro lattice guard + refine JSON soft-fail added |

**Not shippable yet.** Shipping gates are held-out metrics; train progress does not unlock batching.

### Roadmap / how we plan to improve

1. **Train-first placement** — better refine/listen prompts and optional classical polish aimed at “next track start,” validated with multi-run corroboration (temperature 0.0 helps but does not eliminate flips).
2. **Far-miss recovery** — keep gap-fill optional/guarded; corroborate sparse multi-probe behavior on remaining hard train shows before auto-triggering.
3. **Pro escalate guardrails** — preserve well-spaced mid cuts when escalating long under-segmented shows.
4. **Re-score Tier A + holdout** only after train gains stick; fix weak festival multi-artist alignment before using those nights as gates.
5. **Batch Live Bluegrass `todo`** and Archive.org upload only after held-out gates pass.
6. **Phase 2b / 5** — broader DAT corpus RAG / optional specialist models; installable config for other dumps (locked goal in PLAN.md).

See [CHANGELOG.md](CHANGELOG.md) and [PLAN.md](PLAN.md) for locked decisions and detailed phases.

## Layout

| Path | Purpose |
|------|---------|
| `src/dat_tracker/` | Library code (catalog, proposals, calibration helpers, …) |
| `scripts/` | Download, score, and build utilities |
| `catalog/` | Show inventory and calibration manifests |
| `data/` | Local media (gitignored): raw dumps, ground truth, work, output |
| `docs/` | Extra notes |
| `tests/` | Pytest suite |

## Usage

These steps assume you are comfortable opening a **terminal**: Terminal.app on macOS, PowerShell or Windows Terminal on Windows, or any shell on Linux. Commands below are meant to be typed (or pasted) there, one block at a time, from the project folder unless noted.

**dat-tracker is still early.** The flow that works today is: install dependencies → put a continuous FLAC on disk → run `scripts/track_show.py` with a [Google AI Studio](https://aistudio.google.com/apikey) API key. Full dump batching and a one-click installer are not ready yet.

### What you need on every OS

| Requirement | Why |
|-------------|-----|
| **Python 3.11+** | Runs the tracker |
| **ffmpeg** (includes **ffprobe** on normal installs) | Decode/cut audio, silence detect, durations |
| **Git** (recommended) | Clone this repository |
| **Gemini API key** | Sparse audio listening (set in a local `.env` file) |
| Disk space | Continuous FLACs and work files are large; plan for tens of GB if you pull calibration or a full dump |

The Python package **`internetarchive`** (Archive.org’s official library / `ia` CLI) is installed automatically when you install this project with `pip`. You do **not** install it separately unless you want it system-wide for other work.

### 1. Get the code

```bash
git clone https://github.com/151henry151/dat-tracker.git
cd dat-tracker
```

If you do not use Git, download the project zip from your host, unzip it, and `cd` into the resulting `dat-tracker` folder.

### 2. Install system tools (pick your OS)

#### Windows

1. Install **Python 3.11+** from [python.org](https://www.python.org/downloads/windows/). In the installer, enable **“Add python.exe to PATH”**.
2. Install **Git** from [git-scm.com](https://git-scm.com/download/win) if you do not have it.
3. Install **ffmpeg** (provides `ffmpeg` and `ffprobe`) using one of:
   - **winget** (Windows 10/11): `winget install --id Gyan.FFmpeg`
   - **Chocolatey**: `choco install ffmpeg`
   - Or download a build from [gyan.dev](https://www.gyan.dev/ffmpeg/builds/) / [BtbN](https://github.com/BtbN/FFmpeg-Builds/releases) and add the `bin` folder to your user **PATH**.
4. Open **PowerShell** or **Windows Terminal** and continue with the confirmation checks below (use `python`, not `python3`).

#### macOS

1. Install **Homebrew** from [brew.sh](https://brew.sh/) if needed.
2. In Terminal:

```bash
brew install python git ffmpeg
```

Homebrew’s `ffmpeg` formula normally includes `ffprobe` on the same PATH. Then run the confirmation checks below (use `python3`).

#### Linux

On Debian/Ubuntu (or a derivative), in a terminal:

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git ffmpeg
```

The `ffmpeg` package normally ships `ffprobe` as well. On other distributions, install the same four packages with your package manager (`python3`, `python3-venv` / venv support, `git`, `ffmpeg`). Then run the confirmation checks below (use `python3`).

#### Confirm system tools

Run these in the same terminal. Version numbers will differ; you mainly care that each command prints a version line and does **not** say “command not found” / “not recognized”.

**Python** — on Windows use `python`; on macOS/Linux use `python3`:

```bash
python3 --version
```

Should return something like:

```text
Python 3.13.5
```

(Any **3.11** or newer is fine.)

**ffmpeg:**

```bash
ffmpeg -version
```

Should return something like (first line is enough; more configuration text usually follows):

```text
ffmpeg version 7.1.3 Copyright (c) 2000-2025 the FFmpeg developers
```

**ffprobe:**

```bash
ffprobe -version
```

Should return something like:

```text
ffprobe version 7.1.3 Copyright (c) 2007-2025 the FFmpeg developers
```

### 3. Create a Python virtual environment and install dat-tracker

Still inside the `dat-tracker` folder.

**macOS / Linux** (bash or zsh):

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
pip install -e ".[asr]"
```

**Windows** (PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
pip install -e ".[asr]"
```

If PowerShell blocks script activation, run once (as yourself, not as a global policy lecture):  
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`  
Or use **Command Prompt** and `.venv\Scripts\activate.bat` instead.

What that install does:

- `-e` installs this repo in “editable” mode so `import dat_tracker` works.
- `.[asr]` pulls in **faster-whisper** for local speech islands (recommended for tracking).
- Core deps including **`internetarchive`**, **`google-genai`**, and **`jsonschema`** come in automatically.

Optional: `pip install -e ".[dev]"` if you also want **pytest** (see Development below). For the review TUI and Accept-all packaging path, install **`[review]`**. Playback uses **`ffplay`** from the ffmpeg package (already required); PortAudio/`sounddevice` is only a fallback if `ffplay` is missing:

```bash
pip install -e ".[asr,review]"
```

You can combine extras: `pip install -e ".[asr,dev,review]"`.

After install, with the venv still **activated**, Archive.org’s CLI should be available:

```bash
ia --help
```

Should return something like:

```text
usage: ia [-h] [-v] [-c FILE] [-l] [-d] [-i] [-H HOST]
          [--user-agent-suffix STRING]
          {command} ...

A command line interface to Archive.org.
```

(More options and subcommands such as `configure`, `download`, and `upload` follow. If you get “command not found”, the venv is probably not activated.)

### 4. Configure your Gemini API key

1. Create an API key in [Google AI Studio](https://aistudio.google.com/apikey). For more than a handful of runs per day, enable billing / prepaid credits on that project (free-tier request caps are easy to hit).
2. Copy the example env file and edit it:

**macOS / Linux:**

```bash
cp .env.example .env
```

**Windows (PowerShell):**

```powershell
Copy-Item .env.example .env
```

3. Open `.env` in a text editor and set:

```text
GEMINI_API_KEY=your_key_here
DAT_TRACKER_LLM_MODEL=gemini-3.6-flash
```

Never commit `.env` (it is gitignored).

### 5. Track one continuous show

Put a continuous FLAC somewhere reachable (for calibration shows the usual path is `data/calibration/<show-id>/synthetic_continuous.flac`). With the venv **activated**:

```bash
python scripts/track_show.py \
  --show-id del2001-04-27.flac16 \
  --artist "Del McCoury Band" \
  --date 2001-04-27 \
  --reuse-calibration-whisper \
  --refine
```

On Windows PowerShell, either use the same line breaks with `` ` `` continuations or write it as one long line.

Useful flags:

| Flag | Meaning |
|------|---------|
| `--source PATH` | Continuous FLAC (default under `data/calibration/<show-id>/`) |
| `--skip-package` | Write the tracking plan only (no track FLAC / txt / ffp export) |
| `--refine` | Second Gemini listen pass (more accurate, more API use) |
| `--gap-fill` | Optional INSERT listen on overlong segments (off by default; use carefully) |
| `--gap-fill-max-seg-sec N` | Segment length that triggers gap-fill probes (default 480) |
| `--reuse-calibration-whisper` | Reuse a cached Whisper JSON under `data/calibration/` when present |
| `--tracker NAME` | Credit string written into show.txt (default `dat-tracker`) |
| `--accept-all` | Headless review Approve-all before packaging (skip the TUI) |
| `--force-unreviewed` | Package without approval (escape hatch only) |

Outputs land under `data/work/<show-id>/` (plan JSON, listen clips, optional `package/`).

### 5b. Review a plan (required before packaging)

```bash
# Easiest: open the show picker (lists data/work plans)
dat-review

# First run (or anytime): set your tracker name (Tracked & Uploaded by)
dat-review --setup-defaults

# Or jump straight to one show
dat-review sbb2001-04-27.flac16

# Headless approve when the auto plan looks good
dat-review sbb2001-04-27.flac16 --accept-all

# Power-user path still works
dat-review --plan data/work/<show-id>/tracking_plan_gemini.json --source path/to.flac
```

On open, `dat-review` hydrates blank track titles/types from Gemini listen notes (when the model left `tracks` empty and only named songs in notes), then runs **one** Gemini companion extract over calibration/ground_truth info text (package fields + setlist; Google Search for missing venue/city/state when artist+date are known; heuristic parse is offline fallback only). That extract reconciles surplus cuts to setlist length, fills blank song titles, and seeds empty package fields, then catalog/`show_id` date. Blank banter/intro/tuning/encore tracks get Jon-style titles (`Banter`, `Intro`, …). Seeded package fields then get a **spelling polish** (known fixes such as `Douglass` → `Douglas`, plus optional Gemini text correction when `GEMINI_API_KEY` is set). Your tracker name comes from saved defaults (`~/.config/dat-tracker/review_defaults.json`, or `catalog/operator_defaults.json`, or `$DAT_TRACKER_DEFAULTS`). `set_label` soft-defaults to `One Set`; `transfer` / `transferer` stay per-show (edit in the review form). CLI `--artist` / `--date` / `--venue` / etc. override those seeds. Batch-check work shows with `uv run python scripts/verify_work_package_seed.py`.

Tracking also writes `data/work/<show-id>/tracking_plan_as_delivered.json` (the LLM lattice before review edits). In the TUI, **Reset to LLM** / `r` restores cuts and track labels from that snapshot and keeps your package metadata.

Waveforms: overview is a multi-row full-show silhouette (yellow cut markers, cyan band = detail window); detail zooms ~±20s around the selected cut with a time ruler.

Keys in the TUI: click a yellow cut on the waveform to select it, then `←`/`→` to nudge by 0.1s (`Shift`±1s, `Ctrl`±0.01s); click elsewhere on the waveform to place the playhead; click a track in the list to select its cut and jump the playhead to that track’s start; `[`/`]` prev/next cut; `a` Accept-all, `s` Save&approve, `r` Reset to LLM, `q` Quit; Space play/pause from the playhead; `l` loop around the selected cut. Insert/delete cut remain on `i`/`d` (hidden from the footer).
### 6. Optional: download from Archive.org

With the venv activated, `ia` comes from the **`internetarchive`** dependency:

```bash
ia configure    # once: archive.org credentials for downloads / uploads
ia download IDENTIFIER --no-directories -C original
```

Project-specific download helpers also live under `scripts/` (see [PLAN.md](PLAN.md) and `docs/`).

## Development

For contributors iterating on the code: same system prerequisites as **Usage** (Python 3.11+, ffmpeg/ffprobe, Git), then a venv with **dev** extras and tests.

Open a terminal, `cd` into the repo, and run the block for your OS.

**macOS / Linux:**

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
pip install -e ".[asr,dev]"
cp .env.example .env   # then set GEMINI_API_KEY
pytest
```

**Windows (PowerShell):**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
pip install -e ".[asr,dev]"
Copy-Item .env.example .env
pytest
```

`pytest` runs the automated test suite. A successful run ends with something like:

```text
.....                                                                    [100%]
XX passed in 0.50s
```

(Exact counts change as tests are added.) Tracking against real audio still needs a valid `.env` and ffmpeg on `PATH`.

Agents and maintainers working in this repo should follow **[PLAN.md](PLAN.md)** and **[AGENTS.md](AGENTS.md)**.

## License

MIT — see [LICENSE](LICENSE).
