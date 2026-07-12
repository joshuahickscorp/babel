from __future__ import annotations

import math
import wave
from pathlib import Path
from typing import Any

from .files import file_sha256


def inspect_wav(path: str | Path, *, silence_floor: float = 0.01) -> dict[str, Any]:
    with wave.open(str(path), "rb") as wav:
        channels = wav.getnchannels()
        sample_rate = wav.getframerate()
        sample_width = wav.getsampwidth()
        frames = wav.getnframes()
        raw = wav.readframes(frames)
    samples = list(_pcm_values(raw, sample_width))
    if not samples:
        raise ValueError(f"{path}: no PCM samples")
    max_abs = float(1 << (sample_width * 8 - 1))
    normalized = [abs(sample) / max_abs for sample in samples]
    clipping_ratio = sum(value >= 0.999 for value in normalized) / len(normalized)
    silence_ratio = sum(value <= silence_floor for value in normalized) / len(normalized)
    rms = math.sqrt(sum(value * value for value in normalized) / len(normalized))
    flags = []
    if sample_rate < 16000:
        flags.append("low_sample_rate")
    if clipping_ratio > 0.01:
        flags.append("clipping")
    if rms < 0.005:
        flags.append("near_silent")
    return {
        "path": str(path),
        "channels": channels,
        "sample_rate_hz": sample_rate,
        "sample_width_bytes": sample_width,
        "frames": frames,
        "duration_s": frames / sample_rate if sample_rate else 0,
        "rms": rms,
        "peak": max(normalized),
        "clipping_ratio": clipping_ratio,
        "silence_ratio": silence_ratio,
        "flags": flags,
    }


def manifest_wavs(
    root: str | Path,
    *,
    source_type: str = "local",
    license_name: str | None = None,
    license_url: str | None = None,
    training_allowed: bool = False,
    eval_allowed: bool = False,
) -> list[dict[str, Any]]:
    rows = []
    for path in sorted(Path(root).rglob("*.wav")):
        info = inspect_wav(path)
        audio_hash = file_sha256(path)
        flags = [*info["flags"]]
        if not license_name:
            flags.append("license_missing")
        rows.append(
            {
                "clip_id": audio_hash[:16],
                "source_id": str(path),
                "source_url": str(path),
                "source_type": source_type,
                "license_name": license_name,
                "license_url": license_url,
                "training_allowed": int(training_allowed and not flags),
                "eval_allowed": int(eval_allowed and not flags),
                "duration_s": info["duration_s"],
                "sample_rate_hz": info["sample_rate_hz"],
                "audio_hash": audio_hash,
                "split": "quarantine" if flags else "unassigned",
                "transcript_type": "unknown",
                "noise_tier": "defective" if info["flags"] else "unknown",
                "notes": ",".join(flags),
            }
        )
    return rows


def _pcm_values(raw: bytes, sample_width: int) -> list[int]:
    if sample_width not in (1, 2, 3, 4):
        raise ValueError(f"unsupported PCM sample width: {sample_width}")
    values = []
    for i in range(0, len(raw), sample_width):
        chunk = raw[i : i + sample_width]
        if len(chunk) != sample_width:
            break
        if sample_width == 1:
            values.append(chunk[0] - 128)
        else:
            value = int.from_bytes(chunk, "little", signed=False)
            sign_bit = 1 << (sample_width * 8 - 1)
            if value & sign_bit:
                value -= 1 << (sample_width * 8)
            values.append(value)
    return values
