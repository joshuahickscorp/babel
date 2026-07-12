from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .audit import ledger_issues, phase_status
from .ledger import coverage, coverage_gaps, experiments, split_leaks


def markdown_report(
    path: str | Path,
    *,
    metrics: Mapping[str, float] | None = None,
    targets: Sequence[Mapping[str, Any]] | None = None,
) -> str:
    status = phase_status(path, metrics)
    cov = coverage(path)
    gaps = coverage_gaps(path, targets) if targets else []
    issues = ledger_issues(path)
    leaks = split_leaks(path)
    recent = experiments(path, 5)
    lines = [
        "# Babel Local Report",
        "",
        "## Stats",
        _kv(status["stats"]),
        "",
        "## Phase Gates",
        _kv(status["checks"]),
        "",
        "## Metrics",
        _kv(metrics or {}),
        "",
        "## Coverage",
        _table(cov[:20]),
        "",
        "## Coverage Gaps",
        _table(gaps[:20]),
        "",
        "## License Issues",
        _table(issues["license"][:20]),
        "",
        "## Defect Issues",
        _table(issues["defects"][:20]),
        "",
        "## Unassigned Eligible Clips",
        _table(issues["unassigned_eligible"][:20]),
        "",
        "## Split Leaks",
        _table(leaks[:20]),
        "",
        "## Recent Experiments",
        _table(recent),
    ]
    return "\n".join(lines).rstrip() + "\n"


def _kv(values: Mapping[str, Any]) -> str:
    return "\n".join(f"- **{key}:** {value}" for key, value in values.items()) or "- none"


def _table(rows: Sequence[Mapping[str, Any]]) -> str:
    if not rows:
        return "- none"
    keys = list(dict.fromkeys(key for row in rows for key in row))
    lines = ["| " + " | ".join(keys) + " |", "| " + " | ".join("---" for _ in keys) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(key, "")) for key in keys) + " |")
    return "\n".join(lines)
