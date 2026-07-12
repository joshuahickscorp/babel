from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .files import file_sha256, load_json
from .ledger import CLIP_COLUMNS, ledger_stats, load_csv_rows, worst_cell_plan


def studio_distillation_plan(
    path: str | Path,
    *,
    metrics: Mapping[str, Any],
    preflight_receipt: str | Path,
    worst_cell_plan_receipt: str | Path,
    previous_metrics: Mapping[str, Any] | None = None,
    manifest_csv: str | Path | None = None,
    target_profile: str = "mac_studio_m1_ultra_128gb",
    host_profile: str = "pre_studio_verifier",
    teacher: str = "openai/whisper-large-v3-turbo",
    student: str = "openai/whisper-tiny",
    seeds: Sequence[int] = (13, 29, 47),
    top_cells: int = 4,
    epochs: int = 3,
    batch_size: int = 4,
    lr: float = 3e-6,
    encoder_lr: float = 1e-6,
    eval_limit: int = 0,
    output_receipt: str | Path | None = None,
) -> dict[str, Any]:
    if not seeds:
        raise ValueError("at least one seed is required")
    if top_cells < 1:
        raise ValueError("top_cells must be at least 1")
    if epochs < 1:
        raise ValueError("epochs must be at least 1")
    if batch_size < 1:
        raise ValueError("batch_size must be at least 1")
    if eval_limit < 0:
        raise ValueError("eval_limit cannot be negative")
    per_group = metrics.get("by_accent_family")
    if not isinstance(per_group, Mapping) or not per_group:
        raise ValueError("studio-distillation-plan requires metrics.by_accent_family")
    for key in ("worst_group_wer", "parity_gap"):
        if metrics.get(key) is None:
            raise ValueError(f"studio-distillation-plan requires metrics.{key}")

    preflight = load_json(preflight_receipt)
    worst_plan = load_json(worst_cell_plan_receipt)
    rows = worst_plan.get("rows") if isinstance(worst_plan, Mapping) else worst_plan
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)) or not rows:
        raise ValueError("worst-cell plan receipt must contain rows")
    ranked_rows = [dict(row) for row in rows if isinstance(row, Mapping)]
    if not ranked_rows:
        raise ValueError("worst-cell plan rows must be objects")
    selected = sorted(ranked_rows, key=lambda row: int(row.get("rank", 10**9)))[:top_cells]
    stats = ledger_stats(path)
    license_summary = (
        _manifest_license_summary(manifest_csv)
        if manifest_csv
        else {"summary": "manifest not provided; run is blocked for public claims until license summary is attached"}
    )
    preflight_passed = bool(isinstance(preflight, Mapping) and preflight.get("passed"))
    host_is_target = host_profile == target_profile
    zero_hour_cells = [
        {
            "accent_family": str(row.get("accent_family") or "unknown"),
            "train_hours": float(row.get("train_hours") or 0.0),
            "group_metric": float(row.get("group_metric") or 0.0),
            "recommended_action": str(row.get("recommended_action") or "inspect"),
        }
        for row in selected
        if float(row.get("train_hours") or 0.0) <= 0.0
    ]
    blockers = []
    if not preflight_passed:
        blockers.append("compute_preflight_receipt_not_green")
    if not host_is_target:
        blockers.append("host_profile_is_not_target_studio")
    group_dro_blockers = [
        "group_dro_sampler_and_loss_receipts_not_implemented",
        "run tiny train-to-score first and record worst-group WER before parity optimization",
    ]
    if zero_hour_cells:
        group_dro_blockers.append("licensed training audio missing for selected worst cells")
    license_text = str(license_summary.get("summary") or "license summary not recorded").replace("'", "")

    seed_commands = []
    for seed in seeds:
        tag = f"studio_tiny_full_seed_{seed}"
        ckpt = f"models/{tag}"
        train_command = (
            f"SEED={seed} PYTHONHASHSEED={seed} "
            f".venv/bin/python scripts/local_scout_distill.py --device mps "
            f"--teacher {teacher} --student {student} --mini-shards 0 "
            f"--epochs {epochs} --batch-size {batch_size} --lr {lr:g} --encoder-lr {encoder_lr:g} "
            f"--save-every 100 --log-every 10 --max-seconds 0 --ckpt {ckpt}"
        )
        eval_command = (
            f".venv/bin/babel local-eval --model {ckpt}/stage_a_flagship "
            f"--tag {tag} --device mps --limit {eval_limit}"
        )
        metrics_path = f"eval/baseline/{tag}.metrics.json"
        heldout_path = f"eval/baseline/{tag}.held_out.jsonl"
        receipt_path = f"benchmark/receipts/{tag}_2026_07_08.experiment.json"
        run_cycle_command = (
            f".venv/bin/babel run-cycle archive/ledger.sqlite {metrics_path} "
            f"--experiment-id {tag}_2026_07_08 "
            f"--exact-command '{train_command}; {eval_command}' "
            f"--component acoustic_distillation_studio "
            f"--hypothesis 'Studio tiny seed {seed} must improve worst-group WER or be recorded as non-release evidence.' "
            f"--split 'full held-out eval; score-and-cite benchmark manifest' "
            f"--license-summary '{license_text}' "
            f"--previous-json eval/baseline/tiny_baseline.metrics.json "
            f"--heldout-jsonl {heldout_path} "
            f"--output-receipt {receipt_path} "
            f"--decision reject_unless_release_gate_passes"
        )
        quality_cards_command = (
            f".venv/bin/babel quality-cards {heldout_path} --metrics-json {metrics_path} "
            f"--manifest-csv benchmark/manifest.csv --output-dir benchmark/QUALITY_CARDS "
            f"--model-name {tag} --release-decision-json {receipt_path} --receipt-path {receipt_path} "
            f"--card-id {tag}"
        )
        seed_commands.append(
            {
                "seed": seed,
                "tag": tag,
                "train_command": train_command,
                "eval_command": eval_command,
                "run_cycle_command": run_cycle_command,
                "quality_cards_command": quality_cards_command,
                "required_outputs": [metrics_path, heldout_path, receipt_path],
            }
        )

    plan = {
        "plan_id": "wave2_studio_distillation_plan_2026_07_08",
        "governing_metric": "worst-group WER and min-max parity gap",
        "target_profile": target_profile,
        "host_profile": host_profile,
        "launch_authorized_on_this_host": preflight_passed and host_is_target,
        "tiny_train_to_score": {
            "status": "authorized" if preflight_passed and host_is_target else "studio_only",
            "commands": seed_commands,
            "post_run_gates": [
                "validate-receipts must pass",
                "worst_group_wer must not regress against previous baseline",
                "parity_gap must not regress against previous baseline",
                "quality cards must exist for every scored accent family",
                "babel_loses_here.md must add or preserve failure rows",
            ],
        },
        "release_expectation": {
            "status": "non_release_expected" if zero_hour_cells else "unknown_until_scored",
            "reason": "selected worst cells have no ledgered training hours" if zero_hour_cells else "score first, then decide",
        },
        "group_dro": {
            "status": "blocked",
            "blockers": group_dro_blockers,
            "required_receipt_fields": [
                "sampler weights by accent_family",
                "per-group loss table",
                "per-group WER table",
                "collapse guard readings",
                "exact command",
                "failure example from the worst group",
            ],
        },
        "input_evidence": {
            "preflight_receipt": str(preflight_receipt),
            "preflight_passed": preflight_passed,
            "worst_cell_plan_receipt": str(worst_cell_plan_receipt),
            "baseline_worst_group_wer": metrics["worst_group_wer"],
            "baseline_parity_gap": metrics["parity_gap"],
            "previous_worst_group_wer": previous_metrics.get("worst_group_wer") if previous_metrics else None,
            "previous_parity_gap": previous_metrics.get("parity_gap") if previous_metrics else None,
            "ledger_stats": stats,
            "license_summary": license_summary,
        },
        "selected_worst_cells": selected,
        "zero_hour_worst_cells": zero_hour_cells,
        "blockers": blockers,
        "decision": (
            "ready_to_launch_on_target_studio"
            if preflight_passed and host_is_target
            else "do_not_launch_full_distillation_on_this_host"
        ),
    }
    if output_receipt:
        receipt_path = Path(output_receipt)
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n")
    return plan


def group_dro_schedule(
    path: str | Path,
    *,
    metrics: Mapping[str, Any],
    worst_cell_plan_receipt: str | Path | None = None,
    group_key: str = "accent_family",
    per_group_key: str = "by_accent_family",
    target_hours: float = 10.0,
    target_eval_clips: int = 10,
    max_weight: float = 8.0,
    temperature: float = 1.0,
    top_groups: int = 12,
    studio_plan_receipt: str | Path | None = None,
    exact_command: str = "",
    output_receipt: str | Path | None = None,
) -> dict[str, Any]:
    if group_key not in CLIP_COLUMNS:
        raise ValueError(f"unknown group key: {group_key}")
    if target_hours < 0:
        raise ValueError("target_hours must be non-negative")
    if target_eval_clips < 0:
        raise ValueError("target_eval_clips must be non-negative")
    if max_weight < 1:
        raise ValueError("max_weight must be at least 1")
    if temperature <= 0:
        raise ValueError("temperature must be positive")
    if top_groups < 1:
        raise ValueError("top_groups must be at least 1")
    per_group = metrics.get(per_group_key)
    if not isinstance(per_group, Mapping) or not per_group:
        raise ValueError(f"metrics missing per-group table: {per_group_key}")
    values = [float(value) for value in per_group.values()]
    worst = max(values)
    best = min(values)
    spread = max(1e-9, worst - best)

    live_plan = worst_cell_plan(
        path,
        metrics,
        group_key=group_key,
        per_group_key=per_group_key,
        target_hours=target_hours,
        target_eval_clips=target_eval_clips,
        limit=max(top_groups, len(per_group)),
    )
    receipt_rows = []
    if worst_cell_plan_receipt:
        loaded = load_json(worst_cell_plan_receipt)
        raw_rows = loaded.get("rows") if isinstance(loaded, Mapping) else loaded
        if isinstance(raw_rows, Sequence) and not isinstance(raw_rows, (str, bytes)):
            receipt_rows = [dict(row) for row in raw_rows if isinstance(row, Mapping)]
    by_group = {str(row.get(group_key)): row for row in live_plan}
    for row in receipt_rows:
        by_group.setdefault(str(row.get(group_key)), row)

    rows = []
    for group, raw_score in per_group.items():
        group_name = str(group)
        score = float(raw_score)
        basis = by_group.get(group_name, {})
        train_hours = float(basis.get("train_hours") or 0.0)
        eval_clips = int(basis.get("eval_clips") or 0)
        gap_hours = max(0.0, target_hours - train_hours)
        eval_gap = max(0, target_eval_clips - eval_clips)
        wer_pressure = (score - best) / spread
        scarcity_pressure = (gap_hours / target_hours) if target_hours else 0.0
        eval_pressure = (eval_gap / target_eval_clips) if target_eval_clips else 0.0
        raw_weight = 1.0 + temperature * (2.0 * wer_pressure + scarcity_pressure + 0.5 * eval_pressure)
        weight = min(max_weight, raw_weight)
        if train_hours <= 0.0:
            action = "block_group_dro_until_training_audio_exists"
        elif gap_hours > 0:
            action = "oversample_with_acquisition_backfill"
        elif eval_gap > 0:
            action = "score_more_eval_before_trusting_dro_gain"
        else:
            action = "eligible_for_group_dro_sampling"
        rows.append(
            {
                group_key: group_name,
                "current_group_wer": round(score, 6),
                "train_hours": round(train_hours, 4),
                "eval_clips": eval_clips,
                "gap_hours": round(gap_hours, 4),
                "eval_gap": eval_gap,
                "wer_pressure": round(wer_pressure, 6),
                "scarcity_pressure": round(scarcity_pressure, 6),
                "eval_pressure": round(eval_pressure, 6),
                "sampler_weight": round(weight, 6),
                "recommended_action": action,
            }
        )
    rows.sort(key=lambda row: (row["sampler_weight"], row["current_group_wer"], row["gap_hours"]), reverse=True)
    rows = [{**row, "rank": i + 1} for i, row in enumerate(rows[:top_groups])]
    weight_sum = sum(float(row["sampler_weight"]) for row in rows)
    sampler_distribution = {
        row[group_key]: round(float(row["sampler_weight"]) / weight_sum, 8) if weight_sum else 0.0
        for row in rows
    }
    blocked_groups = [row for row in rows if row["recommended_action"] == "block_group_dro_until_training_audio_exists"]
    blockers = []
    if blocked_groups:
        blockers.append("group_dro_selected_groups_have_zero_training_hours")
    if not exact_command:
        blockers.append("group_dro_exact_training_command_not_recorded")
    if metrics.get("worst_group_wer") is None or metrics.get("parity_gap") is None:
        blockers.append("metrics_missing_worst_group_or_parity")
    if studio_plan_receipt:
        studio_plan = load_json(studio_plan_receipt)
        if isinstance(studio_plan, Mapping) and not studio_plan.get("launch_authorized_on_this_host"):
            blockers.append("studio_plan_refuses_launch_on_this_host")
    result = {
        "schedule_id": "wave3_group_dro_schedule_2026_07_08",
        "governing_metric": "worst-group WER and min-max parity gap",
        "status": "blocked" if blockers else "ready_for_controlled_group_dro_run",
        "blockers": blockers,
        "inputs": {
            "metrics_worst_group_wer": metrics.get("worst_group_wer"),
            "metrics_parity_gap": metrics.get("parity_gap"),
            "per_group_key": f"metrics_json.{per_group_key}",
            "worst_cell_plan_receipt": str(worst_cell_plan_receipt) if worst_cell_plan_receipt else None,
            "studio_plan_receipt": str(studio_plan_receipt) if studio_plan_receipt else None,
            "target_hours": target_hours,
            "target_eval_clips": target_eval_clips,
            "max_weight": max_weight,
            "temperature": temperature,
        },
        "sampler_distribution": sampler_distribution,
        "rows": rows,
        "required_training_receipt_fields": [
            "exact command",
            "commit",
            "split",
            "license summary",
            "sampler weights by accent_family",
            "per-group loss table",
            "collapse guard readings",
            "worst-group WER",
            "per-group WER table",
            "release-gate decision",
            "failure example from the worst group",
        ],
        "exact_command": exact_command or None,
    }
    if output_receipt:
        receipt_path = Path(output_receipt)
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


def acquisition_plan(
    path: str | Path,
    *,
    schedule_receipt: str | Path,
    manifest_csv: str | Path | None = None,
    target_hours: float = 10.0,
    limit: int = 8,
    output_receipt: str | Path | None = None,
) -> dict[str, Any]:
    if target_hours <= 0:
        raise ValueError("target_hours must be positive")
    if limit < 1:
        raise ValueError("limit must be at least 1")
    schedule = load_json(schedule_receipt)
    if not isinstance(schedule, Mapping):
        raise ValueError("schedule receipt must be an object")
    rows = schedule.get("rows")
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)) or not rows:
        raise ValueError("schedule receipt must contain rows")
    manifest_rows = load_csv_rows(manifest_csv) if manifest_csv else []
    manifest_summary = _manifest_license_summary(manifest_csv) if manifest_csv else None
    blocked_hashes = sorted({str(row.get("clip_sha256") or "") for row in manifest_rows if row.get("clip_sha256")})
    blocked_sources = sorted(
        {
            str(row.get("source") or "unknown")
            for row in manifest_rows
            if str(row.get("redistributable") or "").lower() != "yes"
        }
    )
    targets = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        group = str(row.get("accent_family") or row.get("group") or "unknown")
        train_hours = float(row.get("train_hours") or 0.0)
        gap_hours = max(0.0, target_hours - train_hours)
        action = str(row.get("recommended_action") or "")
        if gap_hours <= 0 and "block" not in action:
            continue
        targets.append(
            {
                "accent_family": group,
                "rank": int(row.get("rank") or len(targets) + 1),
                "current_group_wer": row.get("current_group_wer"),
                "sampler_weight": row.get("sampler_weight"),
                "current_train_hours": round(train_hours, 4),
                "target_train_hours": target_hours,
                "hours_to_acquire": round(gap_hours, 4),
                "minimum_new_eval_clips": max(0, int(row.get("eval_gap") or 0)),
                "allowed_sources": [source["source"] for source in _allowed_acquisition_sources()],
                "provenance_gate": {
                    "required_clip_fields": [
                        "clip_id",
                        "source_id",
                        "source_url",
                        "source_type",
                        "license_name",
                        "license_url",
                        "attribution",
                        "audio_hash",
                        "speaker_hash",
                        "accent_family",
                        "split",
                    ],
                    "required_flags": {
                        "training_allowed": 1,
                        "redistribution_allowed": 1,
                        "pii_status": "reviewed_or_clean",
                    },
                    "must_not_match_manifest_audio_hashes": bool(blocked_hashes),
                    "split_rule": "run babel assign-splits after source_id/speaker_hash/audio_hash are populated",
                },
                "license_gate": "manual license text review before ledger-upsert; reject non-commercial, no-derivatives, or missing attribution",
            }
        )
        if len(targets) >= limit:
            break
    result = {
        "plan_id": "wave4_acquisition_plan_2026_07_08",
        "governing_metric": "worst-group WER and min-max parity gap",
        "status": "plan_only_no_download_or_training",
        "schedule_receipt": str(schedule_receipt),
        "manifest_summary": manifest_summary,
        "do_not_train_manifest_hashes": {
            "count": len(blocked_hashes),
            "sources": blocked_sources,
            "reason": "current benchmark/eval audio is score-and-cite or otherwise manifest-frozen",
        },
        "allowed_sources": _allowed_acquisition_sources(),
        "blocked_sources": [
            {
                "source": "afrispeech-200",
                "reason": "CC-BY-NC-SA-4.0 eval rows are score-and-cite only; do not redistribute or use for commercial training",
            },
            {
                "source": "EdACC withdrawn deposit 4836",
                "reason": "governance permits current deposits 10283/8983 only",
            },
        ],
        "targets": targets,
        "pre_compute_gates": [
            "all target rows ledgered with source_id, audio_hash, speaker_hash, split, and license_url",
            "babel audit archive/ledger.sqlite passes",
            "babel split-leaks archive/ledger.sqlite returns empty",
            "babel worst-cell-plan shows nonzero training hours for selected groups",
            "no target audio hash appears in benchmark/manifest.csv",
        ],
    }
    if output_receipt:
        receipt_path = Path(output_receipt)
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


def validate_acquisition_intake(
    rows: Sequence[Mapping[str, Any]],
    *,
    acquisition_plan_receipt: str | Path,
    manifest_csv: str | Path | None = None,
    output_receipt: str | Path | None = None,
) -> dict[str, Any]:
    if not rows:
        raise ValueError("acquisition intake requires at least one candidate row")
    plan = load_json(acquisition_plan_receipt)
    if not isinstance(plan, Mapping):
        raise ValueError("acquisition plan receipt must be an object")
    targets = plan.get("targets")
    if not isinstance(targets, Sequence) or isinstance(targets, (str, bytes)):
        targets = []
    target_groups = {str(row.get("accent_family") or "unknown") for row in targets if isinstance(row, Mapping)}
    allowed_sources = [str(row.get("source") or "") for row in plan.get("allowed_sources", []) if isinstance(row, Mapping)]
    blocked_sources = [str(row.get("source") or "") for row in plan.get("blocked_sources", []) if isinstance(row, Mapping)]
    manifest_rows = load_csv_rows(manifest_csv) if manifest_csv else []
    manifest_hashes = {str(row.get("clip_sha256") or "") for row in manifest_rows if row.get("clip_sha256")}
    required = {
        "clip_id",
        "source_id",
        "source_url",
        "source_type",
        "license_name",
        "license_url",
        "attribution",
        "audio_hash",
        "speaker_hash",
        "accent_family",
        "split",
    }
    accepted, rejected, results = [], [], []
    hours_by_group: dict[str, float] = {}
    for row in rows:
        row_dict = dict(row)
        clip_id = str(row_dict.get("clip_id") or "unknown")
        failures = []
        missing = sorted(field for field in required if not row_dict.get(field))
        failures.extend(f"missing {field}" for field in missing)
        unknown = sorted(set(row_dict) - set(CLIP_COLUMNS))
        failures.extend(f"unknown field {field}" for field in unknown)
        group = str(row_dict.get("accent_family") or "unknown")
        if target_groups and group not in target_groups:
            failures.append(f"accent_family {group!r} is not targeted by acquisition plan")
        source_text = " ".join(
            str(row_dict.get(key) or "")
            for key in ("source_type", "source_id", "source_url", "notes")
        )
        if any(_source_matches(source_text, source) for source in blocked_sources):
            failures.append("source is blocked by acquisition plan")
        if allowed_sources and not any(_source_matches(source_text, source) for source in allowed_sources):
            failures.append("source is not in acquisition plan allowed_sources")
        license_name = str(row_dict.get("license_name") or "")
        if not _license_training_allowed(license_name):
            failures.append("license is not training/redistribution eligible")
        if int(row_dict.get("training_allowed") or 0) != 1:
            failures.append("training_allowed must be 1")
        if int(row_dict.get("redistribution_allowed") or 0) != 1:
            failures.append("redistribution_allowed must be 1")
        pii_status = str(row_dict.get("pii_status") or "")
        if pii_status not in {"clean", "reviewed", "reviewed_or_clean"}:
            failures.append("pii_status must be clean, reviewed, or reviewed_or_clean")
        audio_hash = str(row_dict.get("audio_hash") or "")
        if audio_hash and audio_hash in manifest_hashes:
            failures.append("audio_hash matches frozen benchmark manifest")
        duration = float(row_dict.get("duration_s") or 0.0)
        if duration <= 0:
            failures.append("duration_s must be positive")
        result = {
            "clip_id": clip_id,
            "accent_family": group,
            "passed": not failures,
            "failures": failures,
            "duration_s": duration,
        }
        results.append(result)
        if failures:
            rejected.append(result)
        else:
            accepted.append(result)
            hours_by_group[group] = hours_by_group.get(group, 0.0) + duration / 3600.0
    report = {
        "receipt_id": "wave5_acquisition_intake_gate_2026_07_08",
        "governing_metric": "worst-group WER and min-max parity gap",
        "passed": not rejected,
        "checked": len(results),
        "accepted": len(accepted),
        "rejected": len(rejected),
        "acquisition_plan_receipt": str(acquisition_plan_receipt),
        "manifest_csv": str(manifest_csv) if manifest_csv else None,
        "manifest_hashes_checked": len(manifest_hashes),
        "accepted_hours_by_accent_family": {key: round(value, 6) for key, value in sorted(hours_by_group.items())},
        "failures": [failure for row in rejected for failure in row["failures"]],
        "results": results,
    }
    if output_receipt:
        receipt_path = Path(output_receipt)
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


def _source_matches(source_text: str, source: str) -> bool:
    text = source_text.lower()
    src = source.lower()
    if "afrispeech" in src:
        return "afrispeech" in text
    if "4836" in src:
        return "4836" in text
    if "edacc" in src:
        return "edacc" in text and ("10283" in text or "8983" in text)
    if "slr70" in src:
        return "slr70" in text
    if "speechocean762" in src:
        return "speechocean762" in text or "speech ocean 762" in text
    return src and src in text


def _license_training_allowed(license_name: str) -> bool:
    name = license_name.strip().lower()
    if not name:
        return False
    blocked = ("nc", "non-commercial", "noncommercial", "nd", "no-deriv", "no derivatives")
    if any(token in name for token in blocked):
        return False
    return name in {"cc-by", "cc-by-4.0", "cc-by-sa", "cc-by-sa-4.0", "cc0", "public-domain"}


def benchmark_freeze(
    *,
    manifest_csv: str | Path,
    scorer_py: str | Path,
    governance_md: str | Path | None = None,
    losses_md: str | Path | None = None,
    low_n_threshold: int = 5,
    output_receipt: str | Path | None = None,
) -> dict[str, Any]:
    if low_n_threshold < 1:
        raise ValueError("low_n_threshold must be at least 1")
    rows = load_csv_rows(manifest_csv)
    if not rows:
        raise ValueError("manifest has no rows")
    required = {
        "clip_id",
        "source",
        "source_clip_ref",
        "license",
        "redistributable",
        "attribution",
        "accent_family",
        "split",
        "duration_s",
        "reference_text",
        "clip_sha256",
    }
    failures = []
    for field in sorted(required):
        missing = sum(1 for row in rows if not row.get(field))
        if missing:
            failures.append(f"manifest missing {field}: {missing}")
    clip_ids = [str(row.get("clip_id") or "") for row in rows]
    hashes = [str(row.get("clip_sha256") or "") for row in rows if row.get("clip_sha256")]
    duplicates = sorted({clip_id for clip_id in clip_ids if clip_ids.count(clip_id) > 1 and clip_id})
    duplicate_hashes = sorted({audio_hash for audio_hash in hashes if hashes.count(audio_hash) > 1 and audio_hash})
    if duplicates:
        failures.append(f"duplicate clip_id: {len(duplicates)}")
    if duplicate_hashes:
        failures.append(f"duplicate clip_sha256: {len(duplicate_hashes)}")
    afrispeech_redistributable = [
        row.get("clip_id")
        for row in rows
        if str(row.get("source") or "").lower() == "afrispeech-200"
        and str(row.get("redistributable") or "").lower() == "yes"
    ]
    if afrispeech_redistributable:
        failures.append(f"afrispeech rows marked redistributable: {len(afrispeech_redistributable)}")

    group_counts: dict[str, int] = {}
    license_counts: dict[str, int] = {}
    source_counts: dict[str, int] = {}
    redistributable_counts: dict[str, int] = {}
    split_counts: dict[str, int] = {}
    for row in rows:
        group_counts[str(row.get("accent_family") or "unknown")] = group_counts.get(str(row.get("accent_family") or "unknown"), 0) + 1
        license_counts[str(row.get("license") or "unknown")] = license_counts.get(str(row.get("license") or "unknown"), 0) + 1
        source_counts[str(row.get("source") or "unknown")] = source_counts.get(str(row.get("source") or "unknown"), 0) + 1
        redistributable_counts[str(row.get("redistributable") or "unknown")] = (
            redistributable_counts.get(str(row.get("redistributable") or "unknown"), 0) + 1
        )
        split_counts[str(row.get("split") or "unknown")] = split_counts.get(str(row.get("split") or "unknown"), 0) + 1
    low_n_groups = {group: count for group, count in sorted(group_counts.items()) if count <= low_n_threshold}
    label_review_groups = sorted(
        group for group in group_counts if "," in group or " and " in group.lower() or "(" in group or ")" in group
    )
    scorer_text = Path(scorer_py).read_text()
    version_match = re.search(r"SCORER_VERSION\s*=\s*[\"']([^\"']+)[\"']", scorer_text)
    r3_backend_status = "stubbed" if "raise NotImplementedError" in scorer_text else "implemented"
    hash_list_digest = hashlib.sha256(("\n".join(sorted(hashes)) + "\n").encode()).hexdigest() if hashes else None
    constraints = [
        "headline metric is worst_group_wer; min-max parity gap is the paired gate",
        "average WER is a no-regress guard only",
        "manifest clip_sha256 values are do-not-train hashes",
        "AfriSpeech-200 rows are score-and-cite only and not redistributable",
    ]
    if r3_backend_status == "stubbed":
        constraints.append("R3 one-command scorer still requires the model inference backend to replace the current stub")
    else:
        constraints.append("R3 model scoring path is implemented; scored rows still require exact command, model hash, and device")
    receipt = {
        "receipt_id": "wave6_benchmark_freeze_2026_07_08",
        "governing_metric": "worst-group WER and min-max parity gap",
        "passed": not failures,
        "status": "frozen_with_score_and_cite_constraints" if not failures else "freeze_failed",
        "failures": failures,
        "manifest": {
            "path": str(manifest_csv),
            "sha256": file_sha256(manifest_csv),
            "rows": len(rows),
            "split_counts": dict(sorted(split_counts.items())),
            "source_counts": dict(sorted(source_counts.items())),
            "license_counts": dict(sorted(license_counts.items())),
            "redistributable_counts": dict(sorted(redistributable_counts.items())),
            "do_not_train_hashes": len(hashes),
            "do_not_train_hash_list_sha256": hash_list_digest,
        },
        "scorer": {
            "path": str(scorer_py),
            "sha256": file_sha256(scorer_py),
            "scorer_version": version_match.group(1) if version_match else None,
            "r3_inference_backend_status": r3_backend_status,
        },
        "governance": {
            "path": str(governance_md) if governance_md else None,
            "sha256": file_sha256(governance_md) if governance_md else None,
        },
        "loss_ledger": {
            "path": str(losses_md) if losses_md else None,
            "sha256": file_sha256(losses_md) if losses_md else None,
        },
        "accent_family_counts": dict(sorted(group_counts.items())),
        "low_n_groups": low_n_groups,
        "label_review_groups": label_review_groups,
        "constraints": constraints,
    }
    if output_receipt:
        receipt_path = Path(output_receipt)
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    return receipt


def _allowed_acquisition_sources() -> list[dict[str, str]]:
    return [
        {
            "source": "EdACC current deposits 10283/8983",
            "license_requirement": "CC-BY or CC-BY-SA only; reject withdrawn deposit 4836",
            "use": "redistributable public-audio benchmark rows and licensed training backfill",
        },
        {
            "source": "SLR70",
            "license_requirement": "record canonical license text and attribution before ledger-upsert",
            "use": "licensed training/eval backfill when accent labels are defensible",
        },
        {
            "source": "speechocean762",
            "license_requirement": "record canonical license text and attribution before ledger-upsert",
            "use": "licensed training/eval backfill when accent labels are defensible",
        },
    ]


def _manifest_license_summary(manifest_csv: str | Path) -> dict[str, Any]:
    rows = load_csv_rows(manifest_csv)
    licenses = sorted({str(row.get("license") or "unknown") for row in rows})
    redistributable = sorted({str(row.get("redistributable") or "unknown") for row in rows})
    sources = sorted({str(row.get("source") or "unknown") for row in rows})
    return {
        "manifest": str(manifest_csv),
        "rows": len(rows),
        "sources": sources,
        "licenses": licenses,
        "redistributable_values": redistributable,
        "summary": (
            f"{len(rows)} manifest rows; licenses={licenses}; "
            f"redistributable={redistributable}; score-and-cite only when redistributable includes 'no'"
        ),
    }
