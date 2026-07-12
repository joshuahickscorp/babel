from __future__ import annotations

import json
import sqlite3
from collections.abc import Mapping, Sequence
from contextlib import closing
from pathlib import Path
from typing import Any

from .gate import release_gate
from .ledger import init_ledger, record_experiment


def _load_json(path: str | Path) -> Any:
    with Path(path).open() as file:
        return json.load(file)


def run_cycle_receipt(
    path: str | Path,
    *,
    experiment_id: str,
    metrics: Mapping[str, Any],
    exact_command: str,
    component: str,
    hypothesis: str,
    split: str,
    license_summary: Mapping[str, Any] | str,
    previous_metrics: Mapping[str, Any] | None = None,
    heldout_rows: Sequence[Mapping[str, Any]] | None = None,
    per_group_key: str = "by_accent_family",
    reference_key: str = "reference",
    hypothesis_key: str = "hypothesis",
    score_key: str = "wer",
    decision: str | None = None,
    notes: str = "",
    commit: str | None = None,
    workspace_dirty: bool | None = None,
    output_receipt: str | Path | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    if not exact_command:
        raise ValueError("exact_command is required")
    if not split:
        raise ValueError("split is required")
    metrics_out = _with_worst_group_metrics(metrics, per_group_key)
    gate = (
        release_gate(metrics_out, previous_metrics)
        if previous_metrics is not None
        else {"passed": False, "failures": ["previous metrics not provided"]}
    )
    metrics_out["release_gate_passed"] = gate["passed"]
    metrics_out["release_gate_failures"] = gate["failures"]
    failure = _worst_failure_example(
        heldout_rows or (),
        reference_key=reference_key,
        hypothesis_key=hypothesis_key,
        score_key=score_key,
    )
    license_payload: Mapping[str, Any] | str = license_summary
    data = {
        "exact_command": exact_command,
        "commit": commit,
        "workspace_dirty_at_recording": workspace_dirty,
        "split": split,
        "license_summary": license_payload,
        "per_group_table_key": f"metrics_json.{per_group_key}",
        "release_gate_decision": gate,
        "failure_example": failure,
    }
    row = {
        "experiment_id": experiment_id,
        "hypothesis": hypothesis,
        "component": component,
        "data": json.dumps(data, sort_keys=True),
        "metrics_json": metrics_out,
        "decision": decision or ("release_gate_passed" if gate["passed"] else "release_gate_failed"),
        "notes": notes,
    }
    if created_at:
        row["created_at"] = created_at
    record_experiment(path, **row)
    if output_receipt:
        receipt = dict(row)
        receipt["metrics_json"] = metrics_out
        receipt_path = Path(output_receipt)
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    return {
        "recorded": experiment_id,
        "receipt": str(output_receipt) if output_receipt else None,
        "release_gate": gate,
        "worst_group_wer": metrics_out["worst_group_wer"],
        "parity_gap": metrics_out["parity_gap"],
        "failure_example": failure,
    }


def _with_worst_group_metrics(metrics: Mapping[str, Any], per_group_key: str) -> dict[str, Any]:
    out = dict(metrics)
    per_group = out.get(per_group_key)
    if isinstance(per_group, Mapping) and per_group:
        values = [float(value) for value in per_group.values()]
        out.setdefault("worst_group_wer", max(values))
        out.setdefault("parity_gap", max(values) - min(values))
    missing = [key for key in ("worst_group_wer", "parity_gap") if key not in out]
    if missing:
        raise ValueError(
            "run-cycle requires worst-group proof: "
            + ", ".join(missing)
            + f" missing and {per_group_key!r} was not usable"
        )
    return out


def _worst_failure_example(
    rows: Sequence[Mapping[str, Any]],
    *,
    reference_key: str,
    hypothesis_key: str,
    score_key: str,
) -> dict[str, Any] | None:
    scored = [row for row in rows if row.get(score_key) is not None]
    if not scored:
        return None
    row = max(scored, key=lambda item: float(item.get(score_key, 0.0)))
    keys = (
        "clip_id",
        "accent_family",
        "fluency_tier",
        "noise_tier",
        score_key,
        reference_key,
        hypothesis_key,
        "unsupported_claims",
        "decision",
        "should_clarify",
    )
    return {key: row[key] for key in keys if key in row}


def validate_experiment_receipts(paths: Sequence[str | Path]) -> dict[str, Any]:
    if not paths:
        raise ValueError("at least one receipt path is required")
    results = []
    for path in paths:
        result = _validate_experiment_receipt(Path(path))
        results.append(result)
    return {
        "passed": all(row["passed"] for row in results),
        "checked": len(results),
        "failures": sum(len(row["failures"]) for row in results),
        "results": results,
    }


def _validate_experiment_receipt(path: Path) -> dict[str, Any]:
    failures: list[str] = []
    try:
        row = _load_json(path)
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "path": str(path),
            "experiment_id": None,
            "scope": "unknown",
            "passed": False,
            "failures": [f"unreadable receipt: {exc}"],
        }
    if not isinstance(row, Mapping):
        return {
            "path": str(path),
            "experiment_id": None,
            "scope": "unknown",
            "passed": False,
            "failures": ["receipt root must be an object"],
        }
    data = row.get("data")
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            failures.append("data must be valid JSON")
            data = {}
    if not isinstance(data, Mapping):
        failures.append("data must be an object")
        data = {}
    metrics = row.get("metrics_json") or row.get("metrics")
    if not isinstance(metrics, Mapping):
        failures.append("metrics_json must be an object")
        metrics = {}
    decision = str(row.get("decision") or "")
    if decision == "record_as_reference_only":
        scope = "reference"
    elif decision == "record_as_contract_evidence":
        scope = "contract_evidence"
    else:
        scope = "model_evidence"
    for key in ("experiment_id", "component", "hypothesis", "decision"):
        if not row.get(key):
            failures.append(f"missing {key}")
    for key in ("exact_command", "commit", "split", "license_summary"):
        if not data.get(key):
            failures.append(f"missing data.{key}")
    if "workspace_dirty_at_recording" not in data:
        failures.append("missing data.workspace_dirty_at_recording")
    per_group_key = str(data.get("per_group_table_key") or "")
    if per_group_key.startswith("metrics_json."):
        metric_key = per_group_key.removeprefix("metrics_json.")
        table = metrics.get(metric_key)
        if not isinstance(table, Mapping) or not table:
            failures.append(f"missing non-empty {per_group_key}")
    elif per_group_key:
        failures.append("data.per_group_table_key must start with metrics_json.")
    elif scope != "contract_evidence":
        failures.append("missing data.per_group_table_key")
    failure_example = data.get("failure_example")
    if not isinstance(failure_example, Mapping) or not failure_example:
        failures.append("missing non-empty data.failure_example")
    else:
        has_reference = any(key in failure_example for key in ("reference", "reference_clean"))
        has_hypothesis = any(key in failure_example for key in ("hypothesis", "hypothesis_clean"))
        has_score = any(key in failure_example for key in ("wer", "clean_wer", "score"))
        if not has_reference:
            failures.append("data.failure_example missing reference")
        if not has_hypothesis:
            failures.append("data.failure_example missing hypothesis")
        if not has_score:
            failures.append("data.failure_example missing score")
    if scope == "contract_evidence":
        contract_metric_key = str(data.get("contract_metric_key") or "")
        has_worst_group_wer = metrics.get("worst_group_wer") is not None and metrics.get("parity_gap") is not None
        if contract_metric_key:
            if not contract_metric_key.startswith("metrics_json."):
                failures.append("data.contract_metric_key must start with metrics_json.")
            else:
                metric_key = contract_metric_key.removeprefix("metrics_json.")
                if metrics.get(metric_key) is None:
                    failures.append(f"missing {contract_metric_key}")
            if metrics.get("parity_gap") is None:
                failures.append("missing metrics_json.parity_gap")
        elif not has_worst_group_wer:
            failures.append("contract evidence requires data.contract_metric_key or worst-group WER metrics")
    else:
        for key in ("release_gate_decision",):
            if not data.get(key):
                failures.append(f"missing data.{key}")
        for key in ("worst_group_wer", "parity_gap"):
            if metrics.get(key) is None:
                failures.append(f"missing metrics_json.{key}")
    if scope == "model_evidence":
        if metrics.get("release_gate_passed") is None:
            failures.append("missing metrics_json.release_gate_passed")
        if not isinstance(data.get("release_gate_decision"), Mapping):
            failures.append("model evidence requires structured data.release_gate_decision")
    return {
        "path": str(path),
        "experiment_id": row.get("experiment_id"),
        "component": row.get("component"),
        "scope": scope,
        "passed": not failures,
        "failures": failures,
    }


def recorded_experiment_metrics(path: str | Path) -> dict[str, Any]:
    init_ledger(path)
    merged: dict[str, Any] = {}
    with closing(sqlite3.connect(path)) as db:
        rows = db.execute(
            """
            select metrics_json
            from experiments
            where metrics_json is not null and metrics_json != ''
            order by created_at, experiment_id
            """
        ).fetchall()
    for (raw,) in rows:
        try:
            parsed = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            continue
        if isinstance(parsed, Mapping):
            merged.update(parsed)
    return merged
