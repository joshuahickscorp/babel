from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def release_gate(current: Mapping[str, float], previous: Mapping[str, float] | None = None) -> dict[str, Any]:
    failures = []
    previous = previous or {}
    lower_is_better = (
        "wer",
        "average_wer",
        "worst_group_wer",
        "parity_gap",
        "hallucination_rate",
        "rtf",
        "tokens_to_first_answer",
        "resident_memory_gb",
        "on_disk_mb",
    )
    higher_is_better = (
        "intent_accuracy",
        "worst_group_intent_accuracy",
        "clarify_precision",
        "clarify_recall",
        "boundary_f1",
        "code_switch_boundary_f1",
    )
    for key in lower_is_better:
        if key in current and key in previous and current[key] > previous[key]:
            failures.append(f"{key} regressed: {current[key]} > {previous[key]}")
    for key in higher_is_better:
        if key in current and key in previous and current[key] < previous[key]:
            failures.append(f"{key} regressed: {current[key]} < {previous[key]}")
    return {"passed": not failures, "failures": failures}


SCORECARD_METRICS = (
    ("average_wer", "Average WER"),
    ("worst_group_wer", "Worst-group WER"),
    ("parity_gap", "Parity gap"),
    ("intent_accuracy", "Intent accuracy"),
    ("worst_group_intent_accuracy", "Worst-group intent accuracy"),
    ("hallucination_rate", "Hallucination rate"),
    ("clarify_precision", "Clarify precision"),
    ("clarify_recall", "Clarify recall"),
    ("boundary_f1", "Boundary F1"),
    ("code_switch_boundary_f1", "Code-switch boundary F1"),
    ("rtf", "RTF"),
    ("tokens_to_first_answer", "Tokens-to-first-answer"),
    ("resident_memory_gb", "Resident memory (GB)"),
    ("on_disk_mb", "On-disk size (MB)"),
    ("license_clean_training_hours", "License-clean training hours"),
)


def scorecard(
    tiers: Mapping[str, Mapping[str, float]],
    previous: Mapping[str, float] | None = None,
) -> dict[str, Any]:
    columns = list(tiers)
    header = ["Metric", *columns] + (["Previous flagship"] if previous is not None else [])
    lines = ["| " + " | ".join(header) + " |", "| " + " | ".join("---" for _ in header) + " |"]
    for key, label in SCORECARD_METRICS:
        cells = [label]
        for column in columns:
            value = tiers[column].get(key)
            cells.append("" if value is None else str(value))
        if previous is not None:
            value = previous.get(key)
            cells.append("" if value is None else str(value))
        lines.append("| " + " | ".join(cells) + " |")
    gate = release_gate(tiers["flagship"], previous) if previous is not None and "flagship" in tiers else None
    return {"table": "\n".join(lines), "gate": gate}
