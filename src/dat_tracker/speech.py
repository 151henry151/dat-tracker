"""Speech-segment helpers for banter-aware boundary candidates."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any


def parse_whisper_segments(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize whisper / faster-whisper JSON segments."""
    segments = payload.get("segments") or []
    out: list[dict[str, Any]] = []
    for seg in segments:
        text = str(seg.get("text") or "").strip()
        out.append(
            {
                "start": float(seg["start"]),
                "end": float(seg["end"]),
                "text": text,
            }
        )
    return out


def cuts_from_speech_segments(
    segments: list[dict[str, Any]],
    *,
    duration_sec: float,
    min_seg_sec: float = 0.5,
) -> list[float]:
    """Turn speech islands into cut candidates at segment edges."""
    cuts = [0.0]
    for seg in segments:
        start = float(seg["start"])
        end = float(seg["end"])
        if end - start < min_seg_sec:
            continue
        for t in (start, end):
            if not cuts or abs(cuts[-1] - t) > 0.05:
                cuts.append(t)
    if duration_sec > 0 and abs(cuts[-1] - duration_sec) > 0.05:
        cuts.append(float(duration_sec))
    return cuts


def transcribe_faster_whisper(
    audio_path: Path,
    *,
    model_size: str = "base",
    language: str = "en",
    device: str = "cpu",
    compute_type: str = "int8",
) -> dict[str, Any]:
    """Transcribe with faster-whisper; return whisper-like JSON segments."""
    from faster_whisper import WhisperModel

    model = WhisperModel(model_size, device=device, compute_type=compute_type)
    segments_iter, _info = model.transcribe(
        str(audio_path), language=language, vad_filter=True
    )
    segments = [
        {
            "start": float(seg.start),
            "end": float(seg.end),
            "text": (seg.text or "").strip(),
        }
        for seg in segments_iter
    ]
    return {"segments": segments}


def transcribe_whisper_cli(
    audio_path: Path,
    *,
    model: str = "base",
    language: str = "en",
) -> dict[str, Any]:
    """Run `whisper` CLI if installed; return parsed JSON payload."""
    out_dir = audio_path.parent / ".whisper"
    out_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "whisper",
            str(audio_path),
            "--model",
            model,
            "--language",
            language,
            "--output_format",
            "json",
            "--output_dir",
            str(out_dir),
            "--verbose",
            "False",
        ],
        check=True,
    )
    json_path = out_dir / f"{audio_path.stem}.json"
    return json.loads(json_path.read_text())
