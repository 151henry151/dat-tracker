## Handoff: dat-tracker calibration quality (do not ship / do not score zip `todo` yet)

You are continuing work on **`/home/henry/dev/dat-tracker`**. Read **`AGENTS.md`** and **`PLAN.md`** first; they are the locked source of truth (shipping gates, sparse Gemini listening, no human waveform UI, no overfitting to Live Bluegrass alone, semver/changelog, no commits unless Henry asks).

### What Henry said (non-negotiable priority)

Quality is **not good enough** to bother evaluating how well tracking works on the **actual untracked FLACs from the Live Bluegrass zip** (the ones Jon has not already split). Stay on **calibration** until results are clearly better. Do **not** batch `todo` dump shows. Do not treat "look at zip FLACs" as the next step.

### Where we are

Pipeline exists and runs end-to-end: classical/ASR candidates → Gemini Flash listen/refine → optional gap-fill INSERT pass → optional Pro escalate for under-segmented long shows → tracking plan JSON under `data/work/<id>/`. Default model: `gemini-3.6-flash`; Pro: `gemini-3.1-pro-preview` via env.

We are far from the locked gates in PLAN.md. Stay at **0.1.0** until gates pass.

### Success criteria (locked in PLAN.md)

Before batching Live Bluegrass `todo`:

1. **Tier B holdout:** mean F1 ≥ **0.85** @ ±15s; no show &lt; **0.70**
2. **Tier A:** mean F1 ≥ **0.80** @ ±15s on ≥3 real raw↔Jon shows
3. Track count: \|hyp − ref\| ≤ 1 on ≥**80%** of those held-out shows
4. Titles may lag; do not block the boundary gate on titles

**Process rule:** tune on **train / few-shot**, not holdout. Weak metrics = pipeline bug to fix, not "add a review UI."

---

## This session (2026-09-09): six commits, real train gains, one important structural finding

Session started at Tier B train mean F1 **0.644** (min 0.500, track `|Δ|≤1` 20%). Ended at mean **0.687** (min 0.522, track `|Δ|≤1` **100%**, passing that gate component). Holdout and Tier A were **not re-run** this session (stale at 0.569 / 0.374 — see "Current scores" below) other than one informational check early on to confirm no tuning leak.

Six commits, in order (`git log` newest first): `748273f`, `400c18c`, `9a6d7ef`, `114b0fb` are this session's; `2a2d6cb`/`d7890a5` predate it.

### 1. Fixed a real bug: `merge_near_duplicate_cuts` was dropping the mandatory show-start cut (commit `114b0fb`)

`merge_near_duplicate_cuts` (`src/dat_tracker/refine_cuts.py`) collapses cut clusters closer than `min_separation_sec`, keeping the *later* time in each cluster. It applied that same rule to the mandatory `0.0` show-start cut: when Gemini accepted a spurious early opening-banter/cheer boundary within the merge window (e.g. 38s), the merge overwrote `0.0` with `38.0` — and the later `ensure_endpoint_cuts()` normalize step then silently re-inserted `0.0`, undoing the merge and leaving the spurious cut in the final plan. This exact pattern showed up independently in 2 of 5 Tier B train shows (`los1997-04-03.kpig`, `ymsb2007-02-24.flac16`).

Fixed: the merge now drops the near-duplicate instead of overwriting a cut already at `0.0`. TDD test: `test_merge_near_duplicate_cuts_drops_spurious_near_zero_cut` in `tests/test_cut_cleanup.py`. **Safe, deterministic, zero API cost to verify, applies automatically to every show.** No regressions on any train or holdout show.

### 2. Fixed gap-fill probe placement — proximity cap + wider clip (commit `114b0fb`)

Diagnosed why gap-fill (`--gap-fill`) never recovered known far-miss boundaries even when it fired: `overlong_gap_probe_centers` snapped each probe to the closest *already-proposed* classical/energy/silence/speech candidate to a geometric target, even when that candidate sat far (100+ seconds in one case) from the target — and the `--gap-fill` listen clip was only ±12s, far too narrow to cover a 35–65s placement error even when the probe landed reasonably close.

Fixed two things:
- Added `max_candidate_offset_sec` (default 90s) to `overlong_gap_probe_centers`: a distant candidate no longer displaces an untethered geometric target that's actually closer to where the missed boundary usually sits.
- Widened the `--gap-fill` listen clip from ±12s to ±45s.

Also added `--gap-fill-max-seg-sec` to `scripts/track_show.py` (was hardcoded at 480s, not configurable from the CLI).

### 3. Tightened the gap-fill INSERT prompt against mid-song false positives (commit `9a6d7ef`)

Real precision risk found in testing: gap-fill inserted a spurious cut into `sbb2001-04-27.flac16`'s ~590s continuous blues song (which Jon tracked as one single track) — the model treated an instrumental/solo section shift as a track boundary. Added explicit guidance to `gap_fill_listen_prompt` (`src/dat_tracker/refine_cuts.py`): a solo/jam/tempo shift inside one long song is **not** a boundary; REJECT unless a concrete new-track marker (applause, spoken word, count-in, a new song starting from a stop) can be named. Also require `insert_decisions.reason` to name that marker rather than accept a vague "section changed."

### 4. Sparse-vs-dense candidate count gates multi-probing (commit `400c18c`)

Deeper diagnosis of why `ymsb2007-02-24.flac16`'s gap-fill still missed a known boundary: its overlong gap actually had **3** already-rejected classical candidates inside it, but the old logic only re-probed the single one nearest a naive geometric midpoint (65.5s from the truth) — never the second-nearest one, which was only 32.5s from the truth and would have been covered by the new ±45s window.

Tried "just re-probe every candidate in the gap" — but `sbb`'s legitimately-continuous long song has **6** candidates spread through it just as evenly as ymsb's 3; probing all of them would give the model 6 separate chances to hallucinate a false boundary in one real song. Temporal isolation (spacing between candidates) doesn't discriminate the two cases — raw **count** does. Added `sparse_candidate_limit` (default 3) to `overlong_gap_probe_centers`: a gap with `<= 3` candidates probes *all* of them; a gap with more stays on the original conservative single nearest-to-target probe. TDD-covered with both real shapes as regression tests (`tests/test_gap_fill_probes.py`).

### 5. Lowered Gemini `generate_content` temperature 0.2 → 0.0 — the important structural fix (commit `748273f`)

**This is probably the most valuable change this session, and it wasn't originally planned — it was chased down after a confusing batch of failed experiments.** Re-running the *same* show through the pipeline with *no relevant code change* was swinging Tier B train F1 by up to 0.2–0.3 in either direction (documented in real time while debugging: sbb alone was observed at 0.667, 0.750, 0.800, and 0.889 across different runs this session, with no code difference relevant to sbb in some of those comparisons). This made single-run "did that help?" judgments unreliable all session — several apparent wins or regressions turned out, on closer inspection (checking whether the model's own notes cited the mechanism under test), to be unrelated noise.

Lowered `temperature=0.2` → `0.0` on both Gemini `generate_content` call sites in `src/dat_tracker/gemini_tracker.py` (first-listen and the shared refine/gap-fill retry helper). Validated: re-ran `lke2006-11-10.early` twice with identical flags at `temperature=0.0` — **F1 was bit-for-bit identical (0.720) both times**, with nearly-identical individual cut times too, versus F1 swinging 0.560–0.720 across earlier `temperature=0.2` runs of the same show.

**Caveat — this does not fully eliminate variance.** `los1997-04-03.kpig`, re-run twice at `temperature=0.0` with identical flags, still swung F1 0.571 → 0.769. So `temperature=0.0` measurably reduces noise but a real audio-judgment ambiguity can still flip the model's decision on some shows. **Any future tuning session should still corroborate a result with 2+ fresh runs before trusting a single score** — just with more confidence than before this fix.

### 6. Segue guidance added to the first-listen prompt — unconfirmed, keep it anyway (commit `748273f`)

Real over-segmentation observed in `los1997-04-03.kpig`: the model correctly heard "song finishes, count-in starts next song" and split there — but Jon's reference package kept that pair as one **segued** track (etree convention: "Song A > Song B" in one physical file, marked with `>`, not a hard split). The tracking-plan schema already has an unused `segue_into_next` field for exactly this, but the old prompt had **no instruction** telling the model when to use it — it actively said "two clear song sections with ... count-in between should be split," with no segue exception.

Added explicit segue guidance to `tracking_listen_prompt` (`src/dat_tracker/listen_clips.py`): a song flowing directly into the next with no real pause (no dead air, no applause, no banter) is a segue, not a boundary — REJECT the cut and mark `segue_into_next=true` instead. TDD test: `test_tracking_listen_prompt_calls_out_segues` in `tests/test_listen_clips.py`.

**Important honesty note:** the los F1 improvement that originally motivated keeping this (0.714 → 0.769) turned out, on inspection of the model's own notes, to have **zero "segue" citations** — it was unrelated run-to-run noise, discovered only because three *other* shows regressed simultaneously with the same prompt change and also had zero segue citations in their notes. The guidance is still worth keeping (it fills a real, well-motivated gap matching PLAN.md's stated convention), but **it has no confirmed causal evidence of changing any real model decision yet.** Don't cite it as a proven win without checking a run's notes for actual segue reasoning first.

### Current scores (2026-09-09 end of session)

All train plans on disk are freshly regenerated at `temperature=0.0` — the most trustworthy state this session produced.

| Set | mean F1 @ ±15s | min F1 | track \|Δ\|≤1 | vs gate |
|-----|----------------|--------|---------------|---------|
| Tier B **train** | **0.687** (was 0.644) | 0.522 (was 0.500) | **100%** (was 20%; gate is ≥80% — **passes** this component) | FAIL mean/min (train isn't the gate, but it's the tune target) |
| Tier B **holdout** | 0.569 (stale — still `temperature=0.2` cached plans, not re-run this session) | 0.308 | 40% | FAIL mean≥0.85 / min≥0.70 / trackΔ≥80% |
| Tier A (3 shows) | 0.374 (stale, not re-run) | 0.308 | 33% | FAIL mean≥0.80 |

Train per-show (all at `temperature=0.0`, `--refine`; gap-fill only where noted):

| Show | F1 | Notes |
|------|----|----|
| sbb2001-04-27.flac16 | 0.889 | No gap-fill. Matches the original pre-session baseline. |
| los1997-04-03.kpig | 0.769 | No gap-fill. **Volatile**: reproduced once at 0.769, once at 0.571, across two `temperature=0.0` runs. Don't trust either single number. |
| ymsb2007-02-24.flac16 | 0.533 | No gap-fill. Consistently the min across nearly every run this session — still unresolved (see below). |
| crnml2002-08-30.flac16 | 0.522 | `--gap-fill --gap-fill-max-seg-sec 320`. A `temperature=0.2` run with the same flags once reached 0.609 but could not be reproduced. |
| lke2006-11-10.early | 0.720 | `--gap-fill --gap-fill-max-seg-sec 320`. **Reproduced identically twice** at `temperature=0.0` — the most trustworthy number in this table. |

To reproduce the gap-filled shows: `scripts/track_show.py --show-id <id> --artist "<artist>" --date <date> --reuse-calibration-whisper --skip-package --refine --gap-fill --gap-fill-max-seg-sec 320`. **`scripts/run_tier_b_split.py --split train --refine` does not pass `--gap-fill`**, so re-running the batch script alone will not reproduce crnml/lke's scores.

Plan backups: `data/work/.plan_backup_2026-09-09/` (pre-session originals, plus `.temp0.json`/`.attempt2.json` snapshots from mid-session). Note: some *intermediate* good results (an earlier crnml run at 0.609, an earlier lke run at 0.640) were overwritten by later reruns before being backed up and could not be exactly reproduced afterward — **back up a plan file immediately after any promising run**, before trying anything else on that show.

Tier A (not re-run this session): Doc Watson ~0.44, JMP ~0.38 (Pro run collapsed to 3/11 tracks), YMSB SBD ~0.31. Festival Del/OCMS Tier A extracts are weakly aligned — skip for scoring until alignment is trustworthy.

### ymsb2007-02-24.flac16 — the unresolved case, diagnosed but not fixed

Still the min score all session (0.533, no gap-fill improves it reliably). Its overlong gap `[88.5, 432.0]` hides the real boundary at 331.5s among 3 classical candidates (155.0, 266.0, 364.0), and the sparse-multi-probe fix (item 4 above) *should* catch it in principle — validated the mechanism works on lke — but two fresh `--gap-fill` runs on ymsb itself gave F1 0.429 (worse — an unrelated first-listen miss that run) and F1 0.556 (better — recovered a different boundary, 632.1s). Two other known misses (632.1s, 831.8s) remain inconsistently caught. This needs either several more trials averaged, or a closer look at why ymsb's *first-listen* pass itself is unusually unstable (it's the only show where the very first boundary, 94.9s, was ever missed in a fresh run this session).

### What already hurt / avoid repeating (accumulated across sessions)

- Blind energy/speech gap-fill without Gemini
- Double polish refine
- Early `snap_clearly_early_cuts_to_speech` in the default path (hurt LKE when cut was already at song start)
- Aggressive default `--gap-fill` (tried again this session in a different form — see below)
- Tuning knobs specifically to holdout shows
- Full-show audio upload as the default (PLAN: sparse clips)
- Local audio-LLM on this GPU (weak; out of happy path)
- **Auto-triggering gap-fill for every show, decoupled from `--gap-fill`/escalate, at a low segment-length threshold.** Tried this session before finding the real root cause (item 2 above): the wiring bug was real (gap-fill was silently unreachable in the default train script), but blindly turning it on for every long segment added a false positive on ymsb and caught nothing. Fix the underlying probe-placement/window/prompt problem first (done, items 2–4 above); do not re-enable automatic triggering without re-validating — it is currently still gated behind an explicit `--gap-fill` flag or Pro-escalate's 600s floor, on purpose.
- **Trusting a single fresh pipeline run as evidence for or against a code change.** The whole reason temperature was lowered this session (item 5) — see above for specifics. Corroborate with 2+ runs, or a deterministic/no-API check of the specific mechanism (e.g. a standalone script recomputing candidate pools) when possible.
- **Crediting a prompt change for a score change without checking the model's own notes cite the new guidance.** The segue-prompt false attribution (item 6) is the concrete example — always grep the plan's `notes` for the concept you added before calling a run's score change a win.

### How we think we make progress (suggested order)

1. **Corroborate ymsb** with 3-5 more `--gap-fill --gap-fill-max-seg-sec 320` runs (now cheaper to trust with `temperature=0.0`) before concluding whether the sparse-probe mechanism helps this show or not.
2. **Recover los's volatility** — figure out why the same show swings 0.571-0.769 at `temperature=0.0` with identical flags; likely a genuine audio ambiguity at one specific boundary, worth listening to directly rather than more blind reruns.
3. **Chase near-miss placement** (the original "huge lever" diagnosis from earlier sessions — a snap-to-known-cut oracle jumped train shows to ~0.75-0.83 — never directly tackled this session; all effort went into far-miss recovery via gap-fill instead). crnml still has 2-3 near-misses in the 15-40s range worth a closer look now that runs are less noisy.
4. **Hard-stop Pro track-count collapse** (JMP 3/11 from an earlier session) — guardrails so escalate cannot erase a reasonable mid-cut lattice. Not touched this session.
5. **Only then** re-run/score Tier A (Watson, JMP, YMSB SBD; fix festival align later) and re-check holdout. Holdout is a **once-in-a-while check**, not a tuning loop — it was checked once this session (unchanged, no tuning leak) but not re-run after any of the fixes above.
6. **Only after gates approach:** one holdout check → then dump `todo`. Not before.

Useful commands:

```bash
.venv/bin/python scripts/score_tier_b_plans.py --split train
.venv/bin/python scripts/run_tier_b_split.py --split train --refine   # does NOT pass --gap-fill
.venv/bin/python scripts/track_show.py --show-id <id> --artist "<artist>" --date <date> \
  --reuse-calibration-whisper --skip-package --refine \
  --gap-fill --gap-fill-max-seg-sec 320                                # gap-fill, per-show
.venv/bin/python scripts/score_tier_a_plans.py
.venv/bin/python scripts/prepare_tier_a.py --show-id docwatson2000-07-22.sbd
```

Key code: `src/dat_tracker/track_show.py` (orchestration + trigger heuristics), `gemini_tracker.py` (Gemini calls, temperature, retries), `refine_cuts.py` (post-process snaps/dedupe/gap-fill probe selection + prompts), `listen_clips.py` (first-listen prompt + clip windows). Tier B `catalog/calibration_tier_b.json` + `scripts/run_tier_b_split.py` / `score_tier_b_plans.py`; Tier A `src/dat_tracker/tier_a.py` + `scripts/prepare_tier_a.py` / `score_tier_a_plans.py`. Media under `data/` is gitignored; Tier A `known_cuts.json` may be untracked locally.

### Working style

- TDD for behavior changes (red → green).
- Henry approved committing this session's work; commits use imperative messages with `Co-Authored-By: Claude Sonnet 5` trailers per current session attribution instructions (this replaces the earlier "no AI attribution" note from prior sessions — check current instructions each session).
- Changelog/docs when behavior lands; stay **0.1.0** until gates pass.
- Prefer automatic LLM tracking; treat weak metrics as bugs.
- **Back up a plan file the moment a run produces a good score, before trying anything else on that show.** Learned the hard way this session (lost an intermediate 0.609 crnml result and a 0.640 lke result to later overwrites).

### Immediate next step for you

Corroborate ymsb with several more `--gap-fill` runs now that `temperature=0.0` makes results trustworthy (see "ymsb — the unresolved case" above), or pick up near-miss placement polish (item 3 in "how we think we make progress") — that lever was diagnosed in an earlier session but never directly implemented this one. Do not declare victory from a single noisy run; do not dig into untracked zip FLACs until Henry says calibration is good enough.
