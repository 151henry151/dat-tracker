"""Sparse listening windows: extract short clips around candidate cuts."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any


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
) -> list[dict[str, float | str]]:
    """Build clamped [start,end] windows centered on mid-show candidates/probes."""
    probes = list(probe_centers_sec or [])
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
            "ffmpeg",
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
- candidate: proposed boundary — ACCEPT only if you hear a real track change
  (song ends / new song starts / banter or intro begins as its own track).
- gap_probe: exploratory scrub in a long span — ADD a cut only if you hear a
  missed boundary near the probe center; otherwise ignore.

Clips:
{win_lines}

Listen like a careful human in Audacity.
For each candidate clip, decide ACCEPT, REJECT, or SNAP (± a few seconds).
REJECT when the clip is continuous music, continuous applause with no new track,
or a mid-song energy bump. Typical bluegrass songs are often ~2–6 minutes; a
7–12 minute "song" with no banter may still be one track, but two clear song
sections with applause/count-in between should be split.
Keep stage banter / tuning / intros as their own tracks when distinct.
Mark segues with segue_into_next true when music continues without a real stop.

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
- Prefer fewer correct cuts over keeping every proposal.
- Drop false positives aggressively.
- You may add a cut near a gap_probe if the audio clearly shows a missed boundary.
- track_type is one of: song, banter, tuning, intro, encore_break, unknown.
"""
