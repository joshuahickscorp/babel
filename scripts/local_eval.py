#!/usr/bin/env python3
"""local_eval.py — trustworthy held-out ASR eval, runnable locally on MPS/CPU.

Fixes the bugs in the pod's evalpack.hf_transcribe_fn that biased the numbers:
  - pins language="en", task="transcribe"  (pod let Whisper AUTO-DETECT language on
    accented English -> mis-detection -> inflated WER)
  - device-aware (mps/cpu/cuda), not hardcoded cuda
  - passes attention_mask
  - Whisper-standard text normalization before WER (lowercase, strip punct, collapse ws)

Usage:
  .venv/bin/python scripts/local_eval.py --model openai/whisper-large-v3-turbo
  .venv/bin/python scripts/local_eval.py --model distil-whisper/distil-large-v3.5 --tag distil
  .venv/bin/python scripts/local_eval.py --model /path/to/local/ckpt --tag mycheck

Writes eval/baseline/<tag>.metrics.json and <tag>.held_out.jsonl
"""
from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

import soundfile as sf
import torch
from jiwer import wer as jiwer_wer
from transformers import WhisperForConditionalGeneration, WhisperProcessor

ROOT = Path(__file__).resolve().parent.parent
CLIPS = ROOT / "archive" / "held_out_clips.jsonl"
AUDIO = ROOT / "archive" / "held_out"
OUT = ROOT / "eval" / "baseline"

_PUNCT = re.compile(r"[^\w\s']")
_WS = re.compile(r"\s+")
_SPOKEN_PUNCT = re.compile(
    r"\b(full stop|period|comma|colon|semicolon|forward slash|slash|dash|hyphen|"
    r"open parenthesis|close parenthesis|apostrophe|exclamation mark|question mark)\b",
    re.I,
)
_MEDICAL_EXPAND = re.compile(
    r"\b(mean arterial pressure|central venous pressure|blood pressure|"
    r"heart rate|respiratory rate|oxygen saturation)\b",
    re.I,
)


def norm(t: str) -> str:
    """Whisper-style normalization: lowercase, drop punctuation, collapse whitespace."""
    t = t.lower().strip()
    t = _PUNCT.sub(" ", t)
    return _WS.sub(" ", t).strip()


def lenient_norm(t: str) -> str:
    """Lenient normalization: also strips spoken punctuation and medical expansions.
    Used alongside raw WER to separate acoustic errors from transcript-style mismatch."""
    t = t.lower().strip()
    t = _SPOKEN_PUNCT.sub(" ", t)
    t = t.replace("greater than", " ").replace("less than", " ").replace(" equals ", " ")
    t = _MEDICAL_EXPAND.sub(" ", t)
    t = _PUNCT.sub(" ", t)
    return _WS.sub(" ", t).strip()


def pick_device() -> str:
    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def grouped_wer(rows, key):
    groups: dict[str, list[float]] = {}
    for r in rows:
        groups.setdefault(r.get(key, "unknown"), []).append(r["wer"])
    gmeans = {g: sum(v) / len(v) for g, v in groups.items()}
    return {g: round(v, 4) for g, v in sorted(gmeans.items(), key=lambda kv: -kv[1])}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, help="HF id or local checkpoint dir")
    ap.add_argument("--tag", default=None, help="output file tag (default: derived from model)")
    ap.add_argument("--limit", type=int, default=0, help="cap clips (0 = all 353)")
    ap.add_argument("--device", default=None)
    args = ap.parse_args()

    tag = args.tag or args.model.rstrip("/").split("/")[-1]
    device = args.device or pick_device()
    OUT.mkdir(parents=True, exist_ok=True)

    print(f"[local_eval] model={args.model} tag={tag} device={device}")
    proc = WhisperProcessor.from_pretrained(args.model)
    dtype = torch.float16 if device != "cpu" else torch.float32
    model = WhisperForConditionalGeneration.from_pretrained(args.model, torch_dtype=dtype).to(device).eval()

    clips = [json.loads(l) for l in open(CLIPS) if l.strip()]
    if args.limit:
        clips = clips[: args.limit]

    rows = []
    t0 = time.time()
    for i, c in enumerate(clips):
        wavp = AUDIO / f"{c['clip_id']}.wav"
        if not wavp.exists():
            continue
        audio, _ = sf.read(str(wavp))
        feats = proc(audio, sampling_rate=16000, return_tensors="pt").input_features.to(device).to(dtype)
        with torch.no_grad():
            ids = model.generate(feats, language="en", task="transcribe", max_new_tokens=128)
        hyp = proc.batch_decode(ids, skip_special_tokens=True)[0].strip()
        ref = c["reference"]
        w = jiwer_wer(norm(ref), norm(hyp)) if norm(ref) else 0.0
        w_lenient = jiwer_wer(lenient_norm(ref), lenient_norm(hyp)) if lenient_norm(ref) else 0.0
        rows.append({"reference": ref, "hypothesis": hyp, "wer": round(w, 4),
                     "wer_lenient": round(w_lenient, 4),
                     "accent_family": c.get("accent_family", "unknown"),
                     "fluency_tier": c.get("fluency_tier", "unknown"),
                     "noise_tier": c.get("noise_tier", "unknown")})
        if (i + 1) % 25 == 0:
            avg = sum(r["wer"] for r in rows) / len(rows)
            print(f"  {i+1}/{len(clips)}  running avg WER={avg:.3f}  ({time.time()-t0:.0f}s)", flush=True)

    avg = sum(r["wer"] for r in rows) / len(rows) if rows else 0.0
    avg_lenient = sum(r["wer_lenient"] for r in rows) / len(rows) if rows else 0.0
    by_accent = grouped_wer(rows, "accent_family")
    by_accent_lenient = {g: round(sum(r["wer_lenient"] for r in rows if r.get("accent_family") == g) /
                                   max(1, sum(1 for r in rows if r.get("accent_family") == g)), 4)
                         for g in by_accent}
    worst = max(by_accent.values()) if by_accent else 0.0
    best = min(by_accent.values()) if by_accent else 0.0
    metrics = {
        "model": args.model, "tag": tag, "device": device,
        "eval_utterances": len(rows),
        "average_wer": round(avg, 4),
        "average_wer_lenient": round(avg_lenient, 4),
        "normalization_delta": round(avg - avg_lenient, 4),
        "worst_group_wer": round(worst, 4),
        "parity_gap": round(worst - best, 4),
        "by_accent_family": by_accent,
        "by_accent_family_lenient": by_accent_lenient,
        "by_fluency_tier": grouped_wer(rows, "fluency_tier"),
        "by_noise_tier": grouped_wer(rows, "noise_tier"),
        "wall_seconds": round(time.time() - t0, 1),
    }
    (OUT / f"{tag}.metrics.json").write_text(json.dumps(metrics, indent=2))
    with open(OUT / f"{tag}.held_out.jsonl", "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")

    print(f"\n[local_eval] {tag}: avg_wer={metrics['average_wer']}  lenient={metrics['average_wer_lenient']}  "
          f"worst_group={metrics['worst_group_wer']}  parity_gap={metrics['parity_gap']}  "
          f"n={len(rows)}  ({metrics['wall_seconds']}s)")
    print("  worst accent cells:", dict(list(by_accent.items())[:5]))
    print(f"  -> {OUT / f'{tag}.metrics.json'}")


if __name__ == "__main__":
    main()
