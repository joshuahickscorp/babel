from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from .metrics import normalize_lenient_text, normalize_text, wer

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "eval" / "baseline" / "turbo_baseline.held_out.jsonl"
CLIPS = ROOT / "archive" / "held_out_clips.jsonl"
OUT_JSON = ROOT / "eval" / "baseline" / "turbo_error_report.json"
OUT_MD = ROOT / "eval" / "baseline" / "turbo_error_report.md"

_MEDICAL = re.compile(
    r"\b(qd|q\.d|bid|b\.i\.d|tid|q\s*\d+h|hr|iv|po|bp|cvp|map|rr|sats?|"
    r"mg|mcg|cc|subcu|nebs?|cxr|cbc|af|pvc|dilaudid|ativan|levophed)\b",
    re.I,
)
_SPOKEN_PUNCTUATION = re.compile(
    r"\b(full stop|period|comma|colon|semicolon|forward slash|slash|dash|hyphen|"
    r"open parenthesis|close parenthesis|apostrophe|exclamation mark|question mark)\b",
    re.I,
)


def overlap(left: str, right: str) -> float:
    left_words = set(normalize_text(left).split())
    right_words = set(normalize_text(right).split())
    return len(left_words & right_words) / max(1, len(left_words | right_words))


def row_tags(ref: str, hyp: str, raw_wer: float, lenient_wer: float) -> list[str]:
    tags = []
    if _SPOKEN_PUNCTUATION.search(hyp):
        tags.append("spoken_punctuation")
    if _MEDICAL.search(ref) or _MEDICAL.search(hyp):
        tags.append("medical_style")
    if raw_wer - lenient_wer >= 0.15:
        tags.append("normalization_sensitive")
    if len(normalize_text(ref).split()) <= 5 and raw_wer >= 0.75:
        tags.append("short_clip_high_wer")
    if raw_wer >= 0.9 and overlap(ref, hyp) < 0.25:
        tags.append("possible_hallucination_or_bad_ref")
    return tags or ["plain_asr_error"]


def write_error_report(
    *,
    baseline_jsonl: str | Path = BASE,
    clips_jsonl: str | Path = CLIPS,
    output_json: str | Path = OUT_JSON,
    output_md: str | Path = OUT_MD,
) -> dict[str, Any]:
    baseline_jsonl = Path(baseline_jsonl)
    clips_jsonl = Path(clips_jsonl)
    output_json = Path(output_json)
    output_md = Path(output_md)
    rows = [json.loads(line) for line in baseline_jsonl.read_text().splitlines() if line.strip()]
    clips = [json.loads(line) for line in clips_jsonl.read_text().splitlines() if line.strip()]
    enriched = []
    for index, row in enumerate(rows):
        ref = row["reference"]
        hyp = row["hypothesis"]
        raw = float(row["wer"])
        lenient_ref = normalize_lenient_text(ref)
        lenient = wer(lenient_ref, normalize_lenient_text(hyp), normalize=False) if lenient_ref else 0.0
        enriched.append(
            {
                "clip_id": clips[index]["clip_id"] if index < len(clips) else None,
                "accent_family": row.get("accent_family", "unknown"),
                "raw_wer": round(raw, 4),
                "lenient_wer": round(lenient, 4),
                "delta": round(raw - lenient, 4),
                "tags": row_tags(ref, hyp, raw, lenient),
                "reference": ref,
                "hypothesis": hyp,
            }
        )

    by_tag: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_accent: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in enriched:
        by_accent[item["accent_family"]].append(item)
        for tag in item["tags"]:
            by_tag[tag].append(item)

    summary = {
        "utterances": len(enriched),
        "raw_average_wer": round(sum(item["raw_wer"] for item in enriched) / len(enriched), 4),
        "lenient_average_wer": round(sum(item["lenient_wer"] for item in enriched) / len(enriched), 4),
        "normalization_delta": round(
            sum(item["raw_wer"] - item["lenient_wer"] for item in enriched) / len(enriched),
            4,
        ),
        "tag_counts": {tag: len(items) for tag, items in sorted(by_tag.items())},
        "accent_summary": {
            accent: {
                "n": len(items),
                "raw_wer": round(sum(item["raw_wer"] for item in items) / len(items), 4),
                "lenient_wer": round(sum(item["lenient_wer"] for item in items) / len(items), 4),
            }
            for accent, items in sorted(
                by_accent.items(),
                key=lambda row: -sum(item["raw_wer"] for item in row[1]) / len(row[1]),
            )
        },
        "top_raw_errors": sorted(enriched, key=lambda item: item["raw_wer"], reverse=True)[:30],
        "top_normalization_deltas": sorted(enriched, key=lambda item: item["delta"], reverse=True)[:30],
    }
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(summary, indent=2, sort_keys=True))
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(_error_report_markdown(summary))
    return {"summary": summary, "output_json": str(output_json), "output_md": str(output_md)}


def _error_report_markdown(summary: dict[str, Any]) -> str:
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
        lines.append(f"- {accent}: n={stats['n']}, raw={stats['raw_wer']}, lenient={stats['lenient_wer']}")
    lines.extend(["", "## Top Raw Errors", ""])
    for item in summary["top_raw_errors"][:15]:
        lines.append(
            f"- {item['raw_wer']} ({item['accent_family']}, {', '.join(item['tags'])}) "
            f"`{item['clip_id']}`"
        )
        lines.append(f"  - ref: {_preview(item['reference'])}")
        lines.append(f"  - hyp: {_preview(item['hypothesis'])}")
    lines.extend(["", "## Biggest Normalization Deltas", ""])
    for item in summary["top_normalization_deltas"][:15]:
        lines.append(
            f"- delta={item['delta']} raw={item['raw_wer']} lenient={item['lenient_wer']} "
            f"({item['accent_family']}) `{item['clip_id']}`"
        )
    return "\n".join(lines) + "\n"


def _preview(text: str, limit: int = 180) -> str:
    return text[:limit].replace("\n", " ")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write a held-out baseline error report.")
    parser.add_argument("--baseline-jsonl", default=str(BASE))
    parser.add_argument("--clips-jsonl", default=str(CLIPS))
    parser.add_argument("--output-json", default=str(OUT_JSON))
    parser.add_argument("--output-md", default=str(OUT_MD))
    args = parser.parse_args(argv)
    result = write_error_report(
        baseline_jsonl=args.baseline_jsonl,
        clips_jsonl=args.clips_jsonl,
        output_json=args.output_json,
        output_md=args.output_md,
    )
    print(f"wrote {result['output_json']}")
    print(f"wrote {result['output_md']}")
    return 0
