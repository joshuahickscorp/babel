from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from .metrics import group_mean, normalize_lenient_text, normalize_text, wer

ROOT = Path(__file__).resolve().parents[2]
CLIPS = ROOT / "archive" / "held_out_clips.jsonl"
AUDIO = ROOT / "archive" / "held_out"
OUT = ROOT / "eval" / "baseline"


def pick_device() -> str:
    import torch

    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def grouped_wer(rows, key):
    return group_mean(rows, key, "wer")


def run_local_eval(
    *,
    model_path: str,
    tag: str | None = None,
    limit: int = 0,
    device: str | None = None,
    clips_path: str | Path = CLIPS,
    audio_root: str | Path = AUDIO,
    output_dir: str | Path = OUT,
) -> int:
    import soundfile as sf
    import torch
    from transformers import WhisperForConditionalGeneration, WhisperProcessor

    tag = tag or model_path.rstrip("/").split("/")[-1]
    device = device or pick_device()
    clips_path = Path(clips_path)
    audio_root = Path(audio_root)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    print(f"[local_eval] model={model_path} tag={tag} device={device}")
    proc = WhisperProcessor.from_pretrained(model_path)
    dtype = torch.float16 if device != "cpu" else torch.float32
    model = WhisperForConditionalGeneration.from_pretrained(model_path, torch_dtype=dtype).to(device).eval()

    clips = [json.loads(line) for line in clips_path.read_text().splitlines() if line.strip()]
    if limit:
        clips = clips[:limit]

    rows = []
    start = time.time()
    for i, clip in enumerate(clips):
        wav_path = audio_root / f"{clip['clip_id']}.wav"
        if not wav_path.exists():
            continue
        audio, _ = sf.read(str(wav_path))
        feats = proc(audio, sampling_rate=16000, return_tensors="pt").input_features.to(device).to(dtype)
        with torch.no_grad():
            ids = model.generate(feats, language="en", task="transcribe", max_new_tokens=128)
        hyp = proc.batch_decode(ids, skip_special_tokens=True)[0].strip()
        ref = clip["reference"]
        lenient_ref = normalize_lenient_text(ref)
        row_wer = wer(ref, hyp) if normalize_text(ref) else 0.0
        row_lenient_wer = wer(lenient_ref, normalize_lenient_text(hyp), normalize=False) if lenient_ref else 0.0
        rows.append(
            {
                "clip_id": clip["clip_id"],
                "reference": ref,
                "hypothesis": hyp,
                "wer": round(row_wer, 4),
                "wer_lenient": round(row_lenient_wer, 4),
                "accent_family": clip.get("accent_family", "unknown"),
                "fluency_tier": clip.get("fluency_tier", "unknown"),
                "noise_tier": clip.get("noise_tier", "unknown"),
            }
        )
        if (i + 1) % 25 == 0:
            avg = sum(row["wer"] for row in rows) / len(rows)
            print(f"  {i + 1}/{len(clips)}  running avg WER={avg:.3f}  ({time.time() - start:.0f}s)", flush=True)

    avg = sum(row["wer"] for row in rows) / len(rows) if rows else 0.0
    avg_lenient = sum(row["wer_lenient"] for row in rows) / len(rows) if rows else 0.0
    by_accent = grouped_wer(rows, "accent_family")
    by_accent_lenient = {
        group: round(
            sum(row["wer_lenient"] for row in rows if row.get("accent_family") == group)
            / max(1, sum(1 for row in rows if row.get("accent_family") == group)),
            4,
        )
        for group in by_accent
    }
    worst = max(by_accent.values()) if by_accent else 0.0
    best = min(by_accent.values()) if by_accent else 0.0
    metrics = {
        "model": model_path,
        "tag": tag,
        "device": device,
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
        "wall_seconds": round(time.time() - start, 1),
    }
    (output / f"{tag}.metrics.json").write_text(json.dumps(metrics, indent=2))
    with (output / f"{tag}.held_out.jsonl").open("w") as file:
        for row in rows:
            file.write(json.dumps(row) + "\n")

    print(
        f"\n[local_eval] {tag}: avg_wer={metrics['average_wer']}  "
        f"lenient={metrics['average_wer_lenient']}  "
        f"worst_group={metrics['worst_group_wer']}  parity_gap={metrics['parity_gap']}  "
        f"n={len(rows)}  ({metrics['wall_seconds']}s)"
    )
    print("  worst accent cells:", dict(list(by_accent.items())[:5]))
    print(f"  -> {output / f'{tag}.metrics.json'}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True, help="HF id or local checkpoint dir")
    parser.add_argument("--tag", default=None, help="output file tag (default: derived from model)")
    parser.add_argument("--limit", type=int, default=0, help="cap clips (0 = all 353)")
    parser.add_argument("--device", default=None)
    args = parser.parse_args(argv)
    return run_local_eval(
        model_path=args.model,
        tag=args.tag,
        limit=args.limit,
        device=args.device,
    )
