#!/usr/bin/env python3
"""
score.py  --  The benchmark scorer (R3 one-command contract).

Canonical: STUDIO_MAXIMIZATION_2026_06_27.md §12.9 (the scored-row schema + reproduction
contract) and §13.N4. The metric is WORST-GROUP WER, never average.

This file defines, today:
  * the metric (worst_group_wer + min_max_gap + per-group WER), wired to jiwer, matching
    `babel local-eval`'s grouping convention;
  * the exact I/O contract an outsider runs (§12.9, <=4 steps);
  * the receipt schema written to receipts/<row_id>.json.

The metric/contract are frozen, and the scorer now has two paths:
  * --hyp for pre-computed hypotheses (zero compute, useful for receipts/tests)
  * --model for the R3 one-command path using the same local Whisper stack as `babel local-eval`

Reproduction contract (§12.9, the >=R2 public-row requirement):
  1. checkout the manifest_hash referenced by the row
  2. download the model at model_source, verify model_hash
  3. score.py --model <path> --manifest benchmark/manifest.csv --audio-root archive/held_out
     -- or, today --
     score.py --hyp <hypotheses.jsonl> --manifest benchmark/manifest.csv
  4. compare printed worst_group_wer / min_max_gap to the row (within bootstrap CI)

Usage:
  .venv/bin/python benchmark/score.py --manifest benchmark/manifest.csv \
      --hyp path/to/hyps.jsonl --model-name some-model --row-id some-row
  .venv/bin/python benchmark/score.py --manifest benchmark/manifest.csv \
      --model models/some-checkpoint --audio-root archive/held_out --device mps

Hypotheses JSONL: one object per line, {"clip_id": ..., "hyp": "..."}.
"""
from __future__ import annotations

import argparse
import csv
import datetime as _dt
import hashlib
import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
SRC = REPO / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from babel.metrics import score_pairs  # noqa: E402

SCORER_VERSION = "0.2.0-model-backend"  # bump on any metric-affecting change; recorded in every row
GROUP_KEY = "accent_family"  # the §3 / Group-DRO grouping key; the worst group is over these


# ---- I/O -------------------------------------------------------------------------------
def sha256_of_file(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_manifest(path: pathlib.Path):
    rows = list(csv.DictReader(open(path)))
    return rows, sha256_of_file(path)


def resolve_device(requested: str) -> str:
    if requested != "auto":
        return requested
    import torch
    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def audio_path_for_row(audio_root: pathlib.Path, row: dict) -> pathlib.Path:
    return audio_root / f"{row['clip_id']}.wav"


def transcribe_with_model(
    model_path: str,
    manifest_rows,
    device: str,
    *,
    audio_root: str | pathlib.Path,
    max_new_tokens: int = 128,
    limit: int = 0,
):
    """Load a Whisper-compatible model and transcribe manifest audio by clip_id.

    Heavy imports are deliberately lazy so --hyp scoring remains a lightweight R2 path.
    Audio is resolved as <audio_root>/<clip_id>.wav, matching archive/held_out.
    """
    import soundfile as sf
    import torch
    from transformers import WhisperForConditionalGeneration, WhisperProcessor

    if max_new_tokens < 1:
        raise ValueError("max_new_tokens must be positive")
    if limit < 0:
        raise ValueError("limit cannot be negative")

    device = resolve_device(device)
    audio_root = pathlib.Path(audio_root)
    processor = WhisperProcessor.from_pretrained(model_path)
    dtype = torch.float32 if device == "cpu" else torch.float16
    model = WhisperForConditionalGeneration.from_pretrained(model_path, torch_dtype=dtype).to(device).eval()

    hyp_by_id = {}
    selected_rows = manifest_rows[:limit] if limit else manifest_rows
    for row in selected_rows:
        wav_path = audio_path_for_row(audio_root, row)
        if not wav_path.exists():
            continue
        audio, _sr = sf.read(str(wav_path))
        inputs = processor(audio, sampling_rate=16000, return_tensors="pt")
        feats = inputs.input_features.to(device).to(dtype)
        generate_kwargs = {"language": "en", "task": "transcribe", "max_new_tokens": max_new_tokens}
        if getattr(inputs, "attention_mask", None) is not None:
            generate_kwargs["attention_mask"] = inputs.attention_mask.to(device)
        with torch.no_grad():
            ids = model.generate(feats, **generate_kwargs)
        hyp_by_id[row["clip_id"]] = processor.batch_decode(ids, skip_special_tokens=True)[0].strip()
    return hyp_by_id


def main() -> int:
    ap = argparse.ArgumentParser(description="Babel benchmark scorer (worst-group WER).")
    ap.add_argument("--manifest", default=str(REPO / "benchmark" / "manifest.csv"))
    ap.add_argument("--model", help="path/id of model to score (R3 one-command path)")
    ap.add_argument("--hyp", help="pre-computed hypotheses JSONL {clip_id, hyp} (today's path)")
    ap.add_argument("--audio-root", default=str(REPO / "archive" / "held_out"))
    ap.add_argument("--device", default="auto")
    ap.add_argument("--limit", type=int, default=0, help="score first N manifest rows for smoke runs; 0 = all")
    ap.add_argument("--max-new-tokens", type=int, default=128)
    ap.add_argument("--model-name", default="unnamed")
    ap.add_argument("--model-source", default="")
    ap.add_argument("--tier", default="external", choices=["flagship", "min-size", "external"])
    ap.add_argument("--row-id", default="")
    ap.add_argument("--seeds", type=int, default=1)
    ap.add_argument("--write-receipt", action="store_true",
                    help="write receipts/<row_id>.json (the §12.9 receipt)")
    args = ap.parse_args()

    manifest_path = pathlib.Path(args.manifest)
    if not manifest_path.exists():
        print(f"ERROR: manifest not found: {manifest_path}", file=sys.stderr)
        return 2
    rows, manifest_hash = load_manifest(manifest_path)
    ref_by_id = {r["clip_id"]: r["reference_text"] for r in rows}
    grp_by_id = {r["clip_id"]: r[GROUP_KEY] for r in rows}

    # obtain hypotheses
    if args.hyp:
        hyp_by_id = {}
        for line in open(args.hyp):
            if line.strip():
                o = json.loads(line)
                hyp_by_id[o["clip_id"]] = o.get("hyp", o.get("hypothesis", ""))
    elif args.model:
        hyp_by_id = transcribe_with_model(
            args.model,
            rows,
            args.device,
            audio_root=args.audio_root,
            max_new_tokens=args.max_new_tokens,
            limit=args.limit,
        )
    else:
        print("ERROR: provide --hyp <jsonl> or --model <path>.", file=sys.stderr)
        return 2

    pairs = []
    missing = 0
    for clip_id, ref in ref_by_id.items():
        if clip_id in hyp_by_id:
            pairs.append((grp_by_id[clip_id], ref, hyp_by_id[clip_id]))
        else:
            missing += 1
    if not pairs:
        print("ERROR: no clip_id overlap between manifest and hypotheses.", file=sys.stderr)
        return 3

    metrics = score_pairs(pairs)
    row_id = args.row_id or f"{args.model_name}-{_dt.date.today().isoformat()}"
    receipt = {
        "row_id": row_id,
        "model_name": args.model_name,
        "model_source": args.model_source,
        "tier": args.tier,
        "manifest_hash": manifest_hash,
        "scorer_version": SCORER_VERSION,
        "seeds": args.seeds,
        "n_scored": len(pairs),
        "n_missing": missing,
        "audio_root": str(args.audio_root) if args.model else "",
        "device": args.device,
        "score_limit": args.limit,
        "date_scored": _dt.date.today().isoformat(),
        "repro_grade": "R3-model-path" if args.model else "R2-hypotheses",
        **metrics,
    }

    print(json.dumps({
        "worst_group_wer": metrics["worst_group_wer"],
        "min_max_gap": metrics["min_max_gap"],
        "average_wer": metrics["average_wer"],
        "n_scored": len(pairs),
        "n_missing": missing,
        "manifest_hash": manifest_hash[:16] + "...",
        "scorer_version": SCORER_VERSION,
    }, indent=2))

    if args.write_receipt:
        out = REPO / "benchmark" / "receipts" / f"{row_id}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(receipt, indent=2))
        print(f"wrote receipt {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
