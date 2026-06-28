#!/usr/bin/env python3
"""
score.py  --  The benchmark scorer (R3 one-command contract).  *** SKELETON / STUB ***

Canonical: STUDIO_MAXIMIZATION_2026_06_27.md §12.9 (the scored-row schema + reproduction
contract) and §13.N4. The metric is WORST-GROUP WER, never average.

This file defines, today:
  * the metric (worst_group_wer + min_max_gap + per-group WER), wired to jiwer, matching
    scripts/local_eval.py's grouping convention;
  * the exact I/O contract an outsider runs (§12.9, <=4 steps);
  * the receipt schema written to receipts/<row_id>.json.

What is STUBBED (Studio / extension work, NOT this scaffolding): actually loading a model
and transcribing audio. Transcription is intentionally left as a clearly-marked NotImplemented
hook so the metric/contract are frozen now and only the inference back-end is filled later.
Until then, `score.py` can score a pre-computed hypotheses JSONL (--hyp), which is enough to
freeze scorer_version and exercise the whole metric/receipt path with zero compute.

Reproduction contract (§12.9, the >=R2 public-row requirement):
  1. checkout the manifest_hash referenced by the row
  2. download the model at model_source, verify model_hash
  3. score.py --model <path> --manifest benchmark/manifest.csv   (R3, on a stated device)
     -- or, today --
     score.py --hyp <hypotheses.jsonl> --manifest benchmark/manifest.csv
  4. compare printed worst_group_wer / min_max_gap to the row (within bootstrap CI)

Usage (today, no inference):
  .venv/bin/python benchmark/score.py --manifest benchmark/manifest.csv \
      --hyp path/to/hyps.jsonl --model-name some-model --row-id some-row

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
from collections import defaultdict

SCORER_VERSION = "0.1.0-skeleton"  # bump on any metric-affecting change; recorded in every row

REPO = pathlib.Path(__file__).resolve().parents[1]
GROUP_KEY = "accent_family"  # the §3 / Group-DRO grouping key; the worst group is over these


# ---- text normalization (kept deliberately close to scripts/local_eval.py:norm) ----------
def norm(t: str) -> str:
    import re
    t = (t or "").lower().strip()
    t = re.sub(r"[^a-z0-9' ]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _wer(ref: str, hyp: str) -> float:
    from jiwer import wer as jiwer_wer
    r = norm(ref)
    return float(jiwer_wer(r, norm(hyp))) if r else 0.0


# ---- the metric (worst-group WER + min-max gap) -----------------------------------------
def score_pairs(pairs):
    """pairs: list of (group, ref, hyp). Returns the §12.9 metric block."""
    per_group_refs = defaultdict(list)
    per_group_hyps = defaultdict(list)
    n_per_group = defaultdict(int)
    all_wers = []
    for group, ref, hyp in pairs:
        per_group_refs[group].append(ref)
        per_group_hyps[group].append(hyp)
        n_per_group[group] += 1
        all_wers.append(_wer(ref, hyp))

    per_group_wer = {}
    for g in per_group_refs:
        # micro-average WER within the group (concatenated), matching local_eval.grouped_wer
        from jiwer import wer as jiwer_wer
        refs = " ".join(norm(r) for r in per_group_refs[g]).strip()
        hyps = " ".join(norm(h) for h in per_group_hyps[g]).strip()
        per_group_wer[g] = round(float(jiwer_wer(refs, hyps)) if refs else 0.0, 4)

    worst = max(per_group_wer.values()) if per_group_wer else None
    best = min(per_group_wer.values()) if per_group_wer else None
    avg = round(sum(all_wers) / len(all_wers), 4) if all_wers else None
    return {
        "average_wer": avg,                                   # reported, NEVER the headline
        "worst_group_wer": round(worst, 4) if worst is not None else None,  # THE headline
        "min_max_gap": round(worst - best, 4) if worst is not None else None,
        "per_group_wer": per_group_wer,
        "n_clips_per_group": dict(n_per_group),
    }


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


def transcribe_with_model(model_path: str, manifest_rows, device: str):
    """STUB (Studio/extension): load `model_path`, transcribe each clip's audio, return
    {clip_id: hyp}. Left unimplemented so the metric + contract freeze now and only the
    inference back-end is added later (mirrors scripts/local_eval.py's MPS path)."""
    raise NotImplementedError(
        "score.py inference back-end is a stub. Provide --hyp <hypotheses.jsonl> today, or "
        "wire model loading here for the R3 one-command path (Studio/extension work)."
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Babel benchmark scorer (worst-group WER).")
    ap.add_argument("--manifest", default=str(REPO / "benchmark" / "manifest.csv"))
    ap.add_argument("--model", help="path/id of model to score (R3 one-command path; STUB)")
    ap.add_argument("--hyp", help="pre-computed hypotheses JSONL {clip_id, hyp} (today's path)")
    ap.add_argument("--device", default="mps")
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
        hyp_by_id = transcribe_with_model(args.model, rows, args.device)  # STUB -> raises
    else:
        print("ERROR: provide --hyp <jsonl> (today) or --model <path> (R3 stub).", file=sys.stderr)
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
        "date_scored": _dt.date.today().isoformat(),
        "repro_grade": "R0-stub",  # promote to >=R2 once frozen manifest + model_hash recorded
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
