from __future__ import annotations

import json
import shutil
import sqlite3
from collections.abc import Mapping, Sequence
from contextlib import closing
from pathlib import Path
from typing import Any

from .ledger import init_ledger, ledger_stats, split_leaks
from .receipt import recorded_experiment_metrics


def phase_status(path: str | Path, metrics: Mapping[str, float] | None = None) -> dict[str, Any]:
    stats = ledger_stats(path)
    metrics = {**recorded_experiment_metrics(path), **(metrics or {})}
    leaks = split_leaks(path)
    issues = ledger_issues(path)
    checks = {
        "phase_0_contract_loop": stats["experiments"] > 0,
        "phase_1_eval_seed": stats["eval_clips"] >= 10 or metrics.get("eval_utterances", 0) >= 10,
        "phase_1_repair_gate": "intent_accuracy" in metrics or "clean_wer" in metrics,
        "phase_2_data_gate": stats["train_hours"] > 0 and stats["coverage_cells"] > 0,
        "license_gate": not issues["license"],
        "defect_gate": not issues["defects"],
        "split_gate": not leaks,
        "runpod_ready": (
            stats["train_hours"] > 0
            and stats["eval_clips"] > 0
            and stats["experiments"] > 0
            and not leaks
            and not issues["license"]
            and not issues["defects"]
        ),
    }
    next_needed = [name for name, passed in checks.items() if not passed]
    return {"stats": stats, "checks": checks, "next_needed": next_needed}


def ledger_issues(path: str | Path) -> dict[str, list[dict[str, Any]]]:
    init_ledger(path)
    queries = {
        "license": """
            select clip_id, source_id, split, license_name, license_url, training_allowed, eval_allowed, notes
            from clips
            where (coalesce(training_allowed, 0) = 1 or coalesce(eval_allowed, 0) = 1)
              and (license_name is null or license_name = '')
        """,
        "defects": """
            select clip_id, source_id, split, noise_tier, training_allowed, eval_allowed, notes
            from clips
            where (coalesce(training_allowed, 0) = 1 or coalesce(eval_allowed, 0) = 1)
              and (noise_tier = 'defective' or notes like '%clipping%' or notes like '%near_silent%' or notes like '%low_sample_rate%')
        """,
        "unassigned_eligible": """
            select clip_id, source_id, split, training_allowed, eval_allowed, notes
            from clips
            where (coalesce(training_allowed, 0) = 1 or coalesce(eval_allowed, 0) = 1)
              and (split is null or split = '' or split = 'unassigned')
        """,
    }
    with closing(sqlite3.connect(path)) as db:
        db.row_factory = sqlite3.Row
        return {name: [dict(row) for row in db.execute(sql).fetchall()] for name, sql in queries.items()}


def audit(path: str | Path, metrics: Mapping[str, float] | None = None) -> dict[str, Any]:
    status = phase_status(path, metrics)
    issues = ledger_issues(path)
    leaks = split_leaks(path)
    failures = []
    for name, rows in issues.items():
        if rows and name != "unassigned_eligible":
            failures.append(f"{name}: {len(rows)}")
    if leaks:
        failures.append(f"split_leaks: {len(leaks)}")
    return {
        "passed": not failures,
        "failures": failures,
        "stats": status["stats"],
        "phase_checks": status["checks"],
        "issues": issues,
        "split_leaks": leaks,
    }


def compute_preflight(
    path: str | Path,
    *,
    workspace: str | Path = ".",
    component: str = "acoustic_distillation",
    min_free_gb: float = 60.0,
    metrics: Mapping[str, float] | None = None,
    required_phase_checks: Sequence[str] = (
        "phase_0_contract_loop",
        "phase_1_eval_seed",
        "phase_1_repair_gate",
        "phase_2_data_gate",
        "license_gate",
        "defect_gate",
        "split_gate",
        "runpod_ready",
    ),
    require_experiments: int = 1,
    require_receipts: Sequence[str | Path] = (),
    output_receipt: str | Path | None = None,
) -> dict[str, Any]:
    if min_free_gb < 0:
        raise ValueError("min_free_gb must be non-negative")
    if require_experiments < 0:
        raise ValueError("require_experiments must be non-negative")
    status = phase_status(path, metrics)
    report = audit(path, metrics)
    usage = shutil.disk_usage(workspace)
    free_gb = usage.free / (1024**3)
    receipts = [
        {
            "path": str(receipt),
            "exists": Path(receipt).exists(),
            "size_bytes": Path(receipt).stat().st_size if Path(receipt).exists() else 0,
        }
        for receipt in require_receipts
    ]
    unknown_checks = [name for name in required_phase_checks if name not in status["checks"]]
    phase_results = {
        name: bool(status["checks"].get(name, False))
        for name in required_phase_checks
        if name in status["checks"]
    }
    checks = {
        "disk_gate": free_gb >= min_free_gb,
        "audit_gate": bool(report["passed"]),
        "experiment_receipt_gate": status["stats"]["experiments"] >= require_experiments,
        "required_receipts_gate": all(row["exists"] and row["size_bytes"] > 0 for row in receipts),
        "known_phase_checks_gate": not unknown_checks,
        **phase_results,
    }
    blockers = [name for name, ok in checks.items() if not ok]
    if unknown_checks:
        blockers.extend(f"unknown_phase_check:{name}" for name in unknown_checks)
    result = {
        "component": component,
        "passed": not blockers,
        "blockers": blockers,
        "checks": checks,
        "stats": status["stats"],
        "phase_status": status["checks"],
        "audit_failures": report["failures"],
        "disk": {
            "workspace": str(workspace),
            "free_gb": round(free_gb, 3),
            "min_free_gb": min_free_gb,
        },
        "required_receipts": receipts,
    }
    if output_receipt:
        receipt_path = Path(output_receipt)
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result
