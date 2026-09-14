"""Sparse listening windows: extract short clips around candidate cuts."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

from dat_tracker.ffmpeg_tools import ffmpeg_bin


def load_dotenv_file(path: Path) -> dict[str, str]:
    """Parse a simple KEY=VALUE .env file (no export, no interpolation)."""
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        out[key.strip()] = value.strip().strip("'").strip('"')
    return out


def build_listen_windows(
    candidate_cuts_sec: list[float],
    *,
    duration_sec: float,
    half_window_sec: float = 8.0,
    skip_endpoints: bool = True,
    probe_centers_sec: list[float] | None = None,
    forward_scrub_offset_sec: float = 0.0,
    forward_scrub_half_window_sec: float | None = None,
) -> list[dict[str, float | str]]:
    """Build clamped [start,end] windows centered on mid-show candidates/probes.

    When forward_scrub_offset_sec > 0, also emit a second window per candidate
    centered offset seconds later (role=forward_scrub) so the model can hear
    the next-track start when the proposal sits mid-applause.
    """
    probes = list(probe_centers_sec or [])
    fwd_half = (
        float(forward_scrub_half_window_sec)
        if forward_scrub_half_window_sec is not None
        else float(half_window_sec)
    )
    windows: list[dict[str, float | str]] = []
    for cut in candidate_cuts_sec:
        c = float(cut)
        if skip_endpoints and (c <= 0.05 or abs(c - duration_sec) <= 0.05):
            continue
        start = max(0.0, c - half_window_sec)
        end = min(float(duration_sec), c + half_window_sec)
        if end - start < 0.2:
            continue
        role = (
            "gap_probe"
            if any(abs(c - p) <= 0.05 for p in probes)
            else "candidate"
        )
        windows.append(
            {
                "center_sec": c,
                "start_sec": start,
                "end_sec": end,
                "role": role,
            }
        )
        if forward_scrub_offset_sec > 0 and role == "candidate":
            fc = c + float(forward_scrub_offset_sec)
            if fc >= duration_sec - 0.05:
                continue
            f_start = max(0.0, fc - fwd_half)
            f_end = min(float(duration_sec), fc + fwd_half)
            if f_end - f_start < 0.2:
                continue
            windows.append(
                {
                    "center_sec": fc,
                    "start_sec": f_start,
                    "end_sec": f_end,
                    "role": "forward_scrub",
                }
            )
    return windows


def add_gap_probe_centers(
    anchor_cuts_sec: list[float],
    *,
    duration_sec: float,
    max_gap_sec: float = 240.0,
    probe_step_sec: float = 90.0,
) -> list[float]:
    """Insert scrub points in long spans between anchors (cost-controlled)."""
    ordered = sorted({float(c) for c in anchor_cuts_sec})
    if not ordered or ordered[0] > 0.05:
        ordered = [0.0, *ordered]
    if abs(ordered[-1] - duration_sec) > 0.05:
        ordered.append(float(duration_sec))

    out: list[float] = []
    for left, right in zip(ordered, ordered[1:], strict=False):
        out.append(left)
        gap = right - left
        if gap <= max_gap_sec or probe_step_sec <= 0:
            continue
        t = left + probe_step_sec
        while t < right - 15.0:
            out.append(round(t, 3))
            t += probe_step_sec
    out.append(ordered[-1])
    # Dedupe while preserving order.
    deduped: list[float] = []
    for c in out:
        if not deduped or abs(deduped[-1] - c) > 0.05:
            deduped.append(c)
    return deduped


def extract_audio_clip(
    source: Path,
    dest: Path,
    *,
    start_sec: float,
    end_sec: float,
) -> Path:
    """Losslessly-ish extract [start,end) to a small FLAC for API upload."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    duration = max(0.05, float(end_sec) - float(start_sec))
    subprocess.run(
        [
            ffmpeg_bin(),
            "-y",
            "-ss",
            f"{start_sec:.3f}",
            "-t",
            f"{duration:.3f}",
            "-i",
            str(source),
            "-c:a",
            "flac",
            str(dest),
        ],
        check=True,
        capture_output=True,
    )
    return dest


def parse_model_json(text: str) -> dict[str, Any]:
    """Extract a JSON object from model text (raw or fenced)."""
    raw = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, flags=re.DOTALL)
    if fence:
        raw = fence.group(1)
    else:
        start = raw.find("{")
        end = raw.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("No JSON object found in model response")
        raw = raw[start : end + 1]
    return json.loads(raw)


def tracking_listen_prompt(
    *,
    show_id: str,
    duration_sec: float,
    candidate_cuts_sec: list[float],
    windows: list[dict[str, Any]],
) -> str:
    """Prompt: scrub short clips like a human tracker; emit tracking-plan JSON."""
    win_lines = "\n".join(
        f"- role={w.get('role', 'candidate')} center={float(w['center_sec']):.3f}s "
        f"(file covers {float(w['start_sec']):.3f}–{float(w['end_sec']):.3f}s on the master)"
        for w in windows
    )
    return f"""You are tracking a live concert DAT transfer into etree-style tracks.

Show id: {show_id}
Master duration: {duration_sec:.3f} seconds

Untrusted proposal times (seconds), including endpoints. Many mid-show times are
energy-detector false positives inside a single song — do NOT keep a cut unless
the audio justifies it:
{json.dumps(candidate_cuts_sec)}

You are given short audio clips only (cost control). Roles:
- candidate: proposed boundary — ACCEPT only if this is (near) where the *next*
  track should begin. REJECT mid-song energy bumps and continuous music.
- forward_scrub: clip centered ~25–35s after a candidate. Use it to hear whether
  the real next-track start is *later* than the candidate (common: candidate sits
  on last note / mid-applause; true cut is banter onset or next song count-in).
  If so, SNAP the cut forward to that later start — do not keep the early time.
- gap_probe: exploratory scrub in a long span — ADD a cut only if you hear a
  missed boundary near the probe center; otherwise ignore.

Clips:
{win_lines}

Listen like a careful human in Audacity.
For each candidate, decide ACCEPT, REJECT, or SNAP (± seconds).

CRITICAL placement rule (etree): the cut marks where the *next* track begins —
first word of banter, tuning, count-in, or first note of the next song. Trailing
applause and the previous song's last notes belong on the *previous* track.
Do NOT place a cut on "song ends" / mid-applause if the next track starts later.
A cut that is 15–40 seconds early is a false placement even if a song is ending.

REJECT hatch (required): if the candidate clip (and any forward_scrub twin) shows
continuous music / mid-song energy with no real track change, REJECT. Do not SNAP
onto a later moment just because something happens in the forward clip — inventing
a boundary causes over-segmentation. Only SNAP forward when you can name the new
track start (banter onset, count-in, first note after a real gap).

Few-shot policy examples (text only):
- Wrong: cut at last chord of song A while crowd is still clapping.
- Right: cut at the first spoken word of stage banter, or the count-in / first
  note of song B after that applause (often 15–40s later).
- Wrong: ACCEPT a candidate mid-solo because energy shifted.
- Right: REJECT that candidate; one long song stays one track.
- Wrong: SNAP forward into a solo section because the forward_scrub clip is busy.
- Right: REJECT when neither clip shows a real song/banter boundary.
- Wrong: split a two-sentence "Thanks everybody, this next one's a waltz"
  between-song remark into its own track.
- Right: fold a brief remark like that into the next song's track; only give
  banter its own track for a real stage break (extended talking, tuning,
  band introductions).

Segues (required): when one song flows directly into the next with no real
pause — the next song's count-in or first notes start immediately, no dead
air, no applause, no stage banter breaking it up first — that is a SEGUE, not
a track boundary. REJECT that cut. Mark segue_into_next=true on the current
track instead; etree convention keeps a segued pair as one physical track,
titled "Song A > Song B". Only split when there is a real gap: applause,
stage banter, tuning, or silence between the two songs.

Etree convention: substantial stage banter, tuning, and encore breaks — the
announcer or band talking for several seconds or more, a real tuning-up
passage, a distinct stage break — usually get their *own* track. A brief
transitional remark between one song's end and the next song's start (a few
words, "thanks everybody", a short pause) is often kept attached to the song
it introduces instead — do not add a banter cut for every single song transition
just because speech was detected there. When unsure whether banter is
substantial, prefer the track count that looks like ~1 track per song plus
occasional distinct breaks over one banter track per transition.

Show opening: this same rule applies at the very start. A brief opening
announcement or crowd greeting immediately before the first song ("Welcome
back...", a quick band intro) is often kept attached to the first song as
one track, not split into its own opening-announcement track — do not treat
the first few seconds of speech as automatically deserving a cut just
because it precedes the first song.

Typical bluegrass songs are often ~2–6 minutes; a 7–12 minute song with no
banter may still be one track.

Return ONLY a JSON object matching this shape (no markdown):
{{
  "schema_version": "1.0.0",
  "show_id": "{show_id}",
  "source_path": "PLACEHOLDER",
  "duration_sec": {duration_sec:.3f},
  "cuts_sec": [0.0, ... , {duration_sec:.3f}],
  "tracks": [
    {{
      "index": 1,
      "start_sec": 0.0,
      "end_sec": 12.0,
      "track_type": "song",
      "title": "guess or null",
      "segue_into_next": false,
      "confidence": 0.0,
      "evidence": ["listened_clip@12.0", "REJECT@40.0"]
    }}
  ],
  "overall_confidence": 0.0,
  "needs_review": false,
  "notes": ["brief listen notes including REJECT/ACCEPT/SNAP decisions"]
}}

Rules:
- cuts_sec must start at 0 and end at duration_sec.
- Drop mid-song false positives; keep real song→song and song→banter boundaries.
- Missing a real boundary is as bad as keeping a false one.
- Prefer SNAP forward from applause/song-end onto next-track start over leaving
  an early cut.
- You may add a cut near a gap_probe if the audio clearly shows a missed boundary.
- Prefer "tracks": [] and put ACCEPT/REJECT/SNAP decisions in notes to keep JSON small;
  cuts_sec is required. Titles may be null/omitted when tracks is empty.
- track_type is one of: song, banter, tuning, intro, encore_break, unknown.
"""
