# dat-tracker

**dat-tracker** helps turn a long, continuous live recording (often one big FLAC from a DAT tape) into a finished show package: separate song tracks, an info text file, fingerprints, and tags — ready for Archive.org / etree-style sharing.

The everyday tool is **`dat-review`**: a terminal app that walks you from “here is my folder of FLACs” through automatic tracking, a review screen, packaging, and (if you want) Archive.org upload.

**Status:** early (**0.1.0**). It is usable for trying the flow on your own continuous FLACs. Batch-uploading a whole dump is **not** recommended yet — tracking quality is still being calibrated (see [PLAN.md](PLAN.md)).

---

## Try it out (recommended)

You do **not** need to install Python or clone this repository to try the app. Use a release binary, get a free **Gemini API key**, then run `dat-review`. (Release builds ship with ffmpeg tools bundled.)

### 1. Download `dat-review`

1. Open **[Releases](https://github.com/151henry151/dat-tracker/releases)**.
2. Download the binary for your computer:
   - **Linux:** `dat-review-linux-x86_64`
   - **Windows:** `dat-review-windows-x86_64.exe` *(when attached to the release)*
   - **macOS (Apple Silicon):** `dat-review-macos-arm64` *(when attached to the release)*
3. Put it somewhere convenient (Desktop, Downloads, or a tools folder).

**Linux / macOS:** make it executable once, then run it from a terminal:

```bash
chmod +x dat-review-linux-x86_64   # or dat-review-macos-arm64
./dat-review-linux-x86_64
```

**Windows:** double-click the `.exe`, or run it from PowerShell / Command Prompt in the folder where you saved it:

```powershell
.\dat-review-windows-x86_64.exe
```

If Windows or macOS binaries are not on the latest release yet, use [Install from source](#install-from-source-developers) below, or check back on the Releases page.

### 2. Get a Gemini API key (free to create)

Tracking listens to short audio clips with Google’s **Gemini** API.

1. Open **[Google AI Studio → API keys](https://aistudio.google.com/apikey)** and sign in with a Google account.
2. Create an API key and copy it (treat it like a password).

On first launch, `dat-review` can ask you to paste the key and save it for next time. You can also put it in a `.env` file next to the binary or in the project folder (see [Gemini API key details](#gemini-api-key-details)).

A Free Tier key is enough to try the app. Long shows use several API requests; free daily limits are low — for many shows per day you may need billing in AI Studio. [Billing](https://ai.google.dev/gemini-api/docs/billing) · [pricing](https://ai.google.dev/gemini-api/docs/pricing).

### 3. Run it on your FLACs

1. Start `dat-review` (see step 1).
2. If asked, enter your **tracker name** (how you want to be credited) and paste your **Gemini API key**.
3. Browse to the folder that contains your continuous show FLACs (not a zip — an unzipped folder of `.flac` files).
4. Pick a show from the list:
   - **Enter** on one show → track it (if needed) → open the review screen.
   - **`a`** → **Track all** untracked shows (can take a long time and use API quota).
5. On the review screen, check cuts and titles. When it looks good:
   - **`a`** Accept-all, or **`s`** Save & approve.
6. The app continues into **packaging**, then asks whether to **upload to Archive.org** (you can skip and keep the local package).

Finished packages land under `data/out/<show-id>/` when you run from a project checkout; with a standalone binary, paths follow the working directory you launched from (and any project root you pass with `--root`).

**Tips**

- First track of a long FLAC can take **many minutes** on CPU (speech transcription). The screen shows live progress and elapsed time so it does not look hung.
- You still need **disk space** for work files and exported tracks.
- Press **`q`** in review to return to the show list (you do not have to quit the whole app).

### Common keyboard shortcuts (review screen)

| Key | Action |
|-----|--------|
| Click yellow cut / `[` `]` | Select previous / next cut |
| `←` `→` | Nudge cut (Shift = larger step) |
| Space | Play / pause from the playhead |
| `l` | Loop around the selected cut |
| `a` | Accept-all |
| `s` | Save & approve |
| `r` | Reset cuts/titles to the automatic plan (keeps package fields) |
| `q` | Back to show list / quit as prompted |

---

## What you get

For each show the tool aims to produce:

- Separate **FLAC tracks** with sensible filenames  
- A **show.txt**-style info file (artist, date, venue, source/transfer, setlist)  
- A **fingerprint** file and tags on the audio  
- Optional **Archive.org** upload after you confirm  

Conventions match careful live tracking: banter/tuning/intros as their own tracks, segues marked with `>`, honest transfer/tracker credits.

---

## Gemini API key details

`dat-review` looks for `GEMINI_API_KEY` in the environment or in a `.env` file.

Example `.env`:

```text
GEMINI_API_KEY=your_key_here
DAT_TRACKER_LLM_MODEL=gemini-3.6-flash
```

| Question | Short answer |
|----------|----------------|
| Credit card required to try? | **No** — Free Tier works for a first try |
| Catch on Free Tier? | **Low rate limits** (easy to hit on a long show) |
| Web search for missing venue? | Needs a **paid** Gemini project; without it, companions/heuristic fill still run |

Never commit a real `.env` (it is gitignored in this repo).

---

## Optional: Archive.org login

After you approve a show, packaging can offer upload. Log in inside the TUI (same idea as `ia configure`), or configure the Archive.org CLI yourself if you installed from source. See [`docs/upload-checklist.md`](docs/upload-checklist.md). The app will not silently upload.

---

## Install from source (developers)

Use this if you are changing the code, or if a binary for your OS is not available yet.

### Prerequisites

- **Python 3.11+**
- **ffmpeg** / **ffprobe** / **ffplay** on `PATH` (release binaries bundle these; source installs do not)
- **Git** (recommended)
- **Gemini API key** (as above)

Install ffmpeg for source/dev work:

| OS | Simple install |
|----|----------------|
| **Windows** | `winget install --id Gyan.FFmpeg` or `choco install ffmpeg` |
| **macOS** | `brew install ffmpeg` |
| **Linux (Debian/Ubuntu)** | `sudo apt install -y ffmpeg` |

### Clone and install

```bash
git clone https://github.com/151henry151/dat-tracker.git
cd dat-tracker
```

**macOS / Linux:**

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
pip install -e ".[asr,review]"
cp .env.example .env   # then set GEMINI_API_KEY
dat-review
```

**Windows (PowerShell):**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
pip install -e ".[asr,review]"
Copy-Item .env.example .env
dat-review
```

Extras: `.[asr]` = Whisper speech islands; `.[review]` = Textual TUI; `.[dev]` = pytest. Combine as needed: `pip install -e ".[asr,review,dev]"`.

### Useful `dat-review` flags

```bash
dat-review                          # dump folder → list → track/review
dat-review --dump-root /path/to/flacs
dat-review --work-plans             # existing data/work plans only
dat-review <show-id>                # jump to one show
dat-review <show-id> --accept-all   # approve without opening the TUI
dat-review --setup-defaults         # set tracker name defaults
```

### Low-level: `scripts/track_show.py`

For scripting / calibration (venv activated):

```bash
python scripts/track_show.py \
  --show-id del2001-04-27.flac16 \
  --artist "Del McCoury Band" \
  --date 2001-04-27 \
  --reuse-calibration-whisper \
  --refine
```

| Flag | Meaning |
|------|---------|
| `--source PATH` | Continuous FLAC |
| `--skip-package` | Write tracking plan only |
| `--refine` | Second Gemini listen pass |
| `--gap-fill` | INSERT listen on overlong segments (use carefully) |
| `--accept-all` / `--force-unreviewed` | Packaging review shortcuts |

Outputs: `data/work/<show-id>/`.

### Development / tests

```bash
pip install -e ".[asr,review,dev]"
pytest
```

Maintainers and agents: follow **[PLAN.md](PLAN.md)** and **[AGENTS.md](AGENTS.md)**. Release binaries are built with PyInstaller (see `packaging/` and `.github/workflows/release-binaries.yml`).

### Repository layout

| Path | Purpose |
|------|---------|
| `src/dat_tracker/` | Library and TUI |
| `scripts/` | Download, score, track utilities |
| `catalog/` | Show inventory / calibration manifests |
| `data/` | Local media (gitignored): raw, work, out |
| `docs/` | Extra notes (upload checklist, baselines, …) |
| `tests/` | Pytest suite |
| `packaging/` | PyInstaller build for release binaries |

---

## Background (why this exists)

Live DAT → FLAC transfers often arrive as **one long file with no track markers**. Splitting them carefully by hand takes hours per show. Silence detectors and energy peak-pickers help a little on studio albums, but live soundboards keep applause and room tone in the mix — so automatic helpers usually leave you dragging markers in a waveform editor anyway.

**dat-tracker** keeps cheap local proposals (silence, energy, speech islands) as navigation aids, then has an **audio-capable LLM** (Gemini) listen to **short clips** around candidates and produce a structured tracking plan. Packaging always goes through the **`dat-review`** gate (Accept-all or edit-then-approve). Calibration against already-tracked Archive.org shows is how we measure progress; Live Bluegrass is the first proving ground, not the only intended use.

Deeper design notes, shipping gates, and phase plan: **[PLAN.md](PLAN.md)**. History of changes: **[CHANGELOG.md](CHANGELOG.md)**.

### Calibration snapshot (approximate)

Not shippable for dump-wide batch upload yet. Tune on train, gate on holdout.

**Baseline A** ([docs/baseline_a.md](docs/baseline_a.md)): Tier B train mean F1 **0.755**, min **0.533**, track \|Δ\|≤1 **100%**.

| Set | mean F1 @ ±15 s | Notes |
|-----|-----------------|--------|
| Tier B holdout (fresh) | ~0.60 | Gate mean ≥ **0.85**, min ≥ **0.70** — fail |
| Tier A (sample) | ~0.34 | Gate mean ≥ **0.80** — fail |

---

## License

MIT — see [LICENSE](LICENSE).
