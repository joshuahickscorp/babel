#!/usr/bin/env python3
"""Analyze held-out baseline errors and flag eval/style issues.

This is intentionally local-only: it reads the already-produced turbo baseline
and writes a compact report for deciding what to fix before another pod run.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

from jiwer import wer as jiwer_wer

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "eval" / "baseline" / "turbo_baseline.held_out.jsonl"
CLIPS = ROOT / "archive" / "held_out_clips.jsonl"
OUT_JSON = ROOT / "eval" / "baseline" / "turbo_error_report.json"
OUT_MD = ROOT / "eval" / "baseline" / "turbo_error_report.md"

_PUNCT = re.compile(r"[^\w\s']")
_WS = re.compile(r"\s+")
_SPOKEN_PUNCT = re.compile(
    r"\b(full stop|period|comma|colon|semicolon|forward slash|slash|dash|hyphen|"
    r"open parenthesis|close parenthesis|apostrophe)\b",
    re.I,
)
_MEDICAL = re.compile(
    r"\b(qd|q\.d|bid|b\.i\.d|tid|q\s*\d+h|hr|iv|po|bp|cvp|map|rr|sats?|"
    r"mg|mcg|cc|subcu|nebs?|cxr|cbc|af|pvc|dilaudid|ativan|levophed)\b",
    re.I,
)


def norm(text: str) -> str:
    text = text.lower().strip()
    text = _PUNCT.sub(" ", text)
    return _WS.sub(" ", text).strip()


def lenient_norm(text: str) -> str:
    text = text.lower().strip()
    text = _SPOKEN_PUNCT.sub(" ", text)
    text = text.replace("greater than", " ").replace("less than", " ")
    text = text.replace(" equals ", " ")
    text = _PUNCT.sub(" ", text)
    return _WS.sub(" ", text).strip()


def overlap(a: str, b: str) -> float:
    aw = set(norm(a).split())
    bw = set(norm(b).split())
    return len(aw & bw) / max(1, len(aw | bw))


def row_tags(ref: str, hyp: str, raw_wer: float, lenient_wer: float) -> list[str]:
    tags = []
    if _SPOKEN_PUNCT.search(hyp):
        tags.append("spoken_punctuation")
    if _MEDICAL.search(ref) or _MEDICAL.search(hyp):
        tags.append("medical_style")
    if raw_wer - lenient_wer >= 0.15:
        tags.append("normalization_sensitive")
    if len(norm(ref).split()) <= 5 and raw_wer >= 0.75:
        tags.append("short_clip_high_wer")
    if raw_wer >= 0.9 and overlap(ref, hyp) < 0.25:
        tags.append("possible_hallucination_or_bad_ref")
    return tags or ["plain_asr_error"]


def main() -> None:
    rows = [json.loads(line) for line in BASE.read_text().splitlines() if line.strip()]
    clips = [json.loads(line) for line in CLIPS.read_text().splitlines() if line.strip()]
    enriched = []
    for i, row in enumerate(rows):
        ref = row["reference"]
        hyp = row["hypothesis"]
        raw = float(row["wer"])
        lw = jiwer_wer(lenient_norm(ref), lenient_norm(hyp)) if lenient_norm(ref) else 0.0
        item = {
            "clip_id": clips[i]["clip_id"] if i < len(clips) else None,
            "accent_family": row.get("accent_family", "unknown"),
            "raw_wer": round(raw, 4),
            "lenient_wer": round(lw, 4),
            "delta": round(raw - lw, 4),
            "tags": row_tags(ref, hyp, raw, lw),
            "reference": ref,
            "hypothesis": hyp,
        }
        enriched.append(item)

    by_tag: dict[str, list[dict]] = defaultdict(list)
    by_accent: dict[str, list[dict]] = defaultdict(list)
    for item in enriched:
        by_accent[item["accent_family"]].append(item)
        for tag in item["tags"]:
            by_tag[tag].append(item)

    summary = {
        "utterances": len(enriched),
        "raw_average_wer": round(sum(x["raw_wer"] for x in enriched) / len(enriched), 4),
        "lenient_average_wer": round(sum(x["lenient_wer"] for x in enriched) / len(enriched), 4),
        "normalization_delta": round(
            sum(x["raw_wer"] - x["lenient_wer"] for x in enriched) / len(enriched), 4
        ),
        "tag_counts": {k: len(v) for k, v in sorted(by_tag.items())},
        "accent_summary": {
            k: {
                "n": len(v),
                "raw_wer": round(sum(x["raw_wer"] for x in v) / len(v), 4),
                "lenient_wer": round(sum(x["lenient_wer"] for x in v) / len(v), 4),
            }
            for k, v in sorted(
                by_accent.items(),
                key=lambda kv: -sum(x["raw_wer"] for x in kv[1]) / len(kv[1]),
            )
        },
        "top_raw_errors": sorted(enriched, key=lambda x: x["raw_wer"], reverse=True)[:30],
        "top_normalization_deltas": sorted(enriched, key=lambda x: x["delta"], reverse=True)[:30],
    }
    OUT_JSON.write_text(json.dumps(summary, indent=2, sort_keys=True))

    lines = [
        "# Turbo Baseline Error Report",
        "",
        f"- utterances: {summary['utterances']}",
        f"- raw average WER: {summary['raw_average_wer']}",
        f"- lenient average WER: {summary['lenient_average_wer']}",
        f"- normalization delta: {summary['normalization_delta']}",
        "",
        "## Tag Counts",
        "",
    ]
    for tag, count in summary["tag_counts"].items():
        lines.append(f"- {tag}: {count}")
    lines.extend(["", "## Worst Accent Groups", ""])
    for accent, stats in list(summary["accent_summary"].items())[:12]:
        lines.append(
            f"- {accent}: n={stats['n']}, raw={stats['raw_wer']}, lenient={stats['lenient_wer']}"
        )
    lines.extend(["", "## Top Raw Errors", ""])
    for item in summary["top_raw_errors"][:15]:
        lines.append(
            f"- {item['raw_wer']} ({item['accent_family']}, {', '.join(item['tags'])}) "
            f"`{item['clip_id']}`"
        )
        lines.append(f"  - ref: {item['reference'][:180].replace(chr(10), ' ')}")
        lines.append(f"  - hyp: {item['hypothesis'][:180].replace(chr(10), ' ')}")
    lines.extend(["", "## Biggest Normalization Deltas", ""])
    for item in summary["top_normalization_deltas"][:15]:
        lines.append(
            f"- delta={item['delta']} raw={item['raw_wer']} lenient={item['lenient_wer']} "
            f"({item['accent_family']}) `{item['clip_id']}`"
        )
    OUT_MD.write_text("\n".join(lines) + "\n")
    print(f"wrote {OUT_JSON}")
    print(f"wrote {OUT_MD}")


if __name__ == "__main__":
    main()
