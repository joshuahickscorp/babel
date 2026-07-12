from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .metrics import cer, eval_repair, wer


def quality_cards(
    rows: Sequence[Mapping[str, Any]],
    metrics: Mapping[str, Any],
    *,
    output_dir: str | Path,
    model_name: str,
    release_decision: str | Mapping[str, Any],
    manifest_rows: Sequence[Mapping[str, Any]] = (),
    receipt_path: str | None = None,
    card_id: str = "quality_card",
    group_key: str = "accent_family",
    per_group_key: str = "by_accent_family",
    limit_per_group: int = 5,
    score_key: str = "wer",
    reference_key: str = "reference",
    hypothesis_key: str = "hypothesis",
) -> list[dict[str, Any]]:
    if not rows:
        raise ValueError("quality cards require at least one row")
    if not model_name:
        raise ValueError("model_name is required")
    if limit_per_group < 1:
        raise ValueError("limit_per_group must be at least 1")
    manifest = {str(row.get("clip_id") or row.get("source_clip_ref")): row for row in manifest_rows}
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row.get(group_key) or "unknown"), []).append(row)
    output = Path(output_dir)
    written = []
    per_group = metrics.get(per_group_key) if isinstance(metrics.get(per_group_key), Mapping) else {}
    for group, group_rows in sorted(grouped.items()):
        selected = sorted(
            group_rows,
            key=lambda row: float(row.get(score_key, 0.0) or 0.0),
            reverse=True,
        )[:limit_per_group]
        path = output / _slug(group) / f"{_slug(card_id)}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            _quality_card_markdown(
                group=group,
                rows=selected,
                manifest=manifest,
                model_name=model_name,
                release_decision=release_decision,
                receipt_path=receipt_path,
                group_metric=per_group.get(group),
                metrics=metrics,
                score_key=score_key,
                reference_key=reference_key,
                hypothesis_key=hypothesis_key,
            )
        )
        written.append(
            {
                "accent_family": group,
                "path": str(path),
                "examples": len(selected),
                "worst_score": max(float(row.get(score_key, 0.0) or 0.0) for row in selected),
            }
        )
    return written


def repair_quality_cards(
    rows: Sequence[Mapping[str, Any]],
    *,
    output_dir: str | Path,
    model_name: str,
    release_decision: str | Mapping[str, Any],
    receipt_path: str | None = None,
    output_receipt: str | Path | None = None,
    card_id: str = "repair_quality_card",
    group_key: str = "accent_family",
    reference_key: str = "reference_clean",
    hypothesis_key: str = "hypothesis_clean",
    limit_per_group: int = 5,
    split: str = "synthetic repair seed",
    license_summary: str = "text-only synthetic/illustrative repair eval; no licensed audio",
) -> dict[str, Any]:
    if not rows:
        raise ValueError("repair quality cards require at least one row")
    if not model_name:
        raise ValueError("model_name is required")
    if limit_per_group < 1:
        raise ValueError("limit_per_group must be at least 1")
    metrics = eval_repair(rows, reference_key=reference_key, hypothesis_key=hypothesis_key, group_key=group_key)
    metrics_out = dict(metrics)
    metrics_out["worst_group_wer"] = max(metrics["clean_by_group"].values())
    metrics_out["parity_gap"] = metrics["clean_parity"]["gap"]
    metrics_out["by_accent_family"] = metrics["clean_by_group"]
    enriched = []
    for i, row in enumerate(rows, 1):
        ref = str(row.get(reference_key, ""))
        hyp = str(row.get(hypothesis_key, ""))
        actual = str(row.get("decision") or "answer")
        should_clarify = bool(row.get("should_clarify"))
        unsupported = list(row.get("unsupported_claims") or [])
        row_clean_wer = wer(ref, hyp) if ref or hyp else 0.0
        decision_mismatch = should_clarify != (actual == "clarify")
        enriched.append(
            {
                **dict(row),
                "_repair_id": str(row.get("repair_id") or row.get("clip_id") or f"repair_{i:04d}"),
                "_clean_wer": row_clean_wer,
                "_clean_cer": cer(ref, hyp) if ref or hyp else 0.0,
                "_decision_mismatch": decision_mismatch,
                "_unsupported_claims": unsupported,
                "_faithfulness_failed": bool(unsupported) or decision_mismatch,
            }
        )
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for row in enriched:
        grouped.setdefault(str(row.get(group_key) or "unknown"), []).append(row)
    output = Path(output_dir)
    cards = []
    for group, group_rows in sorted(grouped.items()):
        selected = sorted(group_rows, key=_repair_sort_key, reverse=True)[:limit_per_group]
        path = output / _slug(group) / f"{_slug(card_id)}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            _repair_quality_card_markdown(
                group=group,
                rows=selected,
                metrics=metrics_out,
                model_name=model_name,
                release_decision=release_decision,
                receipt_path=receipt_path,
                split=split,
                license_summary=license_summary,
                reference_key=reference_key,
                hypothesis_key=hypothesis_key,
            )
        )
        cards.append(
            {
                "accent_family": group,
                "path": str(path),
                "examples": len(selected),
                "failures": sum(bool(row.get("_faithfulness_failed")) for row in selected),
                "worst_clean_wer": max(float(row.get("_clean_wer", 0.0)) for row in selected),
            }
        )
    result = {"metrics": metrics_out, "cards": cards, "receipt": str(output_receipt) if output_receipt else None}
    if output_receipt:
        receipt = {
            "model": model_name,
            "release_decision": release_decision,
            "split": split,
            "license_summary": license_summary,
            "source_receipt": receipt_path,
            "metrics": metrics_out,
            "cards": cards,
        }
        receipt_path_out = Path(output_receipt)
        receipt_path_out.parent.mkdir(parents=True, exist_ok=True)
        receipt_path_out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    return result


def _quality_card_markdown(
    *,
    group: str,
    rows: Sequence[Mapping[str, Any]],
    manifest: Mapping[str, Mapping[str, Any]],
    model_name: str,
    release_decision: str | Mapping[str, Any],
    receipt_path: str | None,
    group_metric: Any,
    metrics: Mapping[str, Any],
    score_key: str,
    reference_key: str,
    hypothesis_key: str,
) -> str:
    release_text = json.dumps(release_decision, sort_keys=True) if isinstance(release_decision, Mapping) else str(release_decision)
    lines = [
        f"# Quality Card: {group}",
        "",
        f"- **model:** {model_name}",
        f"- **release_decision:** {release_text}",
        f"- **receipt:** {receipt_path or 'not recorded'}",
        f"- **group_wer:** {group_metric if group_metric is not None else 'not recorded'}",
        f"- **worst_group_wer:** {metrics.get('worst_group_wer', 'not recorded')}",
        f"- **parity_gap:** {metrics.get('parity_gap', 'not recorded')}",
        "",
        "## Worst Examples",
    ]
    for i, row in enumerate(rows, 1):
        clip_id = str(row.get("clip_id") or "unknown")
        m = manifest.get(clip_id, {})
        ref = str(row.get(reference_key, ""))
        hyp = str(row.get(hypothesis_key, ""))
        lines.extend(
            [
                "",
                f"### {i}. `{clip_id}`",
                "",
                f"- **source:** {m.get('source', row.get('source', 'not recorded'))}",
                f"- **split:** {m.get('split', row.get('split', 'not recorded'))}",
                f"- **license:** {m.get('license', row.get('license', 'not recorded'))}",
                f"- **redistributable:** {m.get('redistributable', row.get('redistributable', 'not recorded'))}",
                f"- **WER:** {row.get(score_key, 'not recorded')}",
                f"- **CER:** {round(cer(ref, hyp), 4) if ref or hyp else 'not recorded'}",
                f"- **reference transcript:** {_one_line(ref)}",
                f"- **candidate output:** {_one_line(hyp)}",
                f"- **teacher output:** {_one_line(str(row.get('teacher_hypothesis') or 'not recorded'))}",
                f"- **student output:** {_one_line(str(row.get('student_hypothesis') or hyp or 'not recorded'))}",
                f"- **repair output:** {_one_line(str(row.get('repair_hypothesis') or row.get('hypothesis_clean') or 'not recorded'))}",
                f"- **release decision:** {release_text}",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _repair_sort_key(row: Mapping[str, Any]) -> tuple[float, float, float]:
    unsupported = float(len(row.get("_unsupported_claims") or []))
    mismatch = 1.0 if row.get("_decision_mismatch") else 0.0
    return (unsupported, mismatch, float(row.get("_clean_wer", 0.0)))


def _repair_quality_card_markdown(
    *,
    group: str,
    rows: Sequence[Mapping[str, Any]],
    metrics: Mapping[str, Any],
    model_name: str,
    release_decision: str | Mapping[str, Any],
    receipt_path: str | None,
    split: str,
    license_summary: str,
    reference_key: str,
    hypothesis_key: str,
) -> str:
    release_text = json.dumps(release_decision, sort_keys=True) if isinstance(release_decision, Mapping) else str(release_decision)
    lines = [
        f"# Stage B Repair Card: {group}",
        "",
        f"- **model:** {model_name}",
        f"- **release_decision:** {release_text}",
        f"- **receipt:** {receipt_path or 'not recorded'}",
        f"- **split:** {split}",
        f"- **license:** {license_summary}",
        f"- **clean_wer:** {metrics.get('clean_wer', 'not recorded')}",
        f"- **group_clean_wer:** {metrics.get('clean_by_group', {}).get(group, 'not recorded')}",
        f"- **worst_group_wer:** {metrics.get('worst_group_wer', 'not recorded')}",
        f"- **parity_gap:** {metrics.get('parity_gap', 'not recorded')}",
        f"- **decision_accuracy:** {metrics.get('decision_accuracy', 'not recorded')}",
        f"- **clarify_precision:** {metrics.get('clarify_precision', 'not recorded')}",
        f"- **clarify_recall:** {metrics.get('clarify_recall', 'not recorded')}",
        f"- **hallucination_rate:** {metrics.get('hallucination_rate', 'not recorded')}",
        "",
        "## Faithfulness Examples",
    ]
    for i, row in enumerate(rows, 1):
        ref = str(row.get(reference_key, ""))
        hyp = str(row.get(hypothesis_key, ""))
        unsupported = row.get("_unsupported_claims") or []
        should = bool(row.get("should_clarify"))
        actual = str(row.get("decision") or "answer")
        verdict = "fail" if row.get("_faithfulness_failed") else "pass"
        lines.extend(
            [
                "",
                f"### {i}. `{row.get('_repair_id', 'unknown')}`",
                "",
                f"- **faithfulness:** {verdict}",
                f"- **decision:** {actual}",
                f"- **should_clarify:** {should}",
                f"- **unsupported_claims:** {', '.join(str(item) for item in unsupported) if unsupported else 'none'}",
                f"- **clean WER:** {round(float(row.get('_clean_wer', 0.0)), 4)}",
                f"- **clean CER:** {round(float(row.get('_clean_cer', 0.0)), 4)}",
                f"- **reference_clean:** {_one_line(ref)}",
                f"- **repair output:** {_one_line(hyp)}",
                f"- **release decision:** {release_text}",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _one_line(value: str, *, limit: int = 240) -> str:
    value = re.sub(r"\s+", " ", value).strip()
    if len(value) <= limit:
        return value
    return value[: limit - 3].rstrip() + "..."


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return slug or "unknown"
