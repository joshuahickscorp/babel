from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

from .core import (
    acquisition_plan,
    assign_splits,
    audit,
    benchmark_freeze,
    coverage_gaps,
    coverage,
    compute_preflight,
    eval_asr,
    eval_nbest,
    eval_repair,
    eval_segmentation,
    export_shard,
    experiments,
    group_dro_schedule,
    inspect_wav,
    init_ledger,
    iter_jsonl,
    ledger_stats,
    load_csv_rows,
    load_json,
    markdown_report,
    manifest_wavs,
    phase_status,
    quality_cards,
    record_experiment,
    release_gate,
    repair_hygiene,
    repair_quality_cards,
    review_queue,
    route_stage_a,
    run_cycle_receipt,
    scorecard,
    split_leaks,
    studio_distillation_plan,
    upsert_clips,
    validate_acquisition_intake,
    validate_dir,
    validate_experiment_receipts,
    validate_stage,
    worst_cell_plan,
)


def emit(value: Any) -> None:
    print(json.dumps(value, indent=2, sort_keys=True))


def git_commit() -> str | None:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def git_dirty() -> bool | None:
    try:
        return bool(subprocess.check_output(["git", "status", "--porcelain"], text=True).strip())
    except (OSError, subprocess.CalledProcessError):
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="babel")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("validate-stage")
    p.add_argument("stage", choices=("stage_a", "stage_a5", "stage_b"))
    p.add_argument("json_file")

    p = sub.add_parser("validate-dir")
    p.add_argument("dir")

    p = sub.add_parser("validate-receipts")
    p.add_argument("receipts", nargs="+")
    p.add_argument("--output-json")

    p = sub.add_parser("route")
    p.add_argument("stage_a_json")

    p = sub.add_parser("inspect-wav")
    p.add_argument("wav_file")

    p = sub.add_parser("manifest-wavs")
    p.add_argument("root")
    p.add_argument("--db")
    p.add_argument("--source-type", default="local")
    p.add_argument("--license-name")
    p.add_argument("--license-url")
    p.add_argument("--training-allowed", action="store_true")
    p.add_argument("--eval-allowed", action="store_true")

    p = sub.add_parser("ledger-init")
    p.add_argument("db")

    p = sub.add_parser("ledger-upsert")
    p.add_argument("db")
    p.add_argument("jsonl")

    p = sub.add_parser("coverage")
    p.add_argument("db")
    p.add_argument("dims", nargs="*", default=("accent_family", "fluency_tier", "noise_tier"))

    p = sub.add_parser("coverage-gaps")
    p.add_argument("db")
    p.add_argument("targets_json")

    p = sub.add_parser("worst-cell-plan")
    p.add_argument("db")
    p.add_argument("metrics_json")
    p.add_argument("--group-key", default="accent_family")
    p.add_argument("--per-group-key", default="by_accent_family")
    p.add_argument("--target-hours", type=float, default=10.0)
    p.add_argument("--target-eval-clips", type=int, default=10)
    p.add_argument("--limit", type=int, default=20)

    p = sub.add_parser("group-dro-schedule")
    p.add_argument("db")
    p.add_argument("metrics_json")
    p.add_argument("--worst-cell-plan")
    p.add_argument("--studio-plan")
    p.add_argument("--group-key", default="accent_family")
    p.add_argument("--per-group-key", default="by_accent_family")
    p.add_argument("--target-hours", type=float, default=10.0)
    p.add_argument("--target-eval-clips", type=int, default=10)
    p.add_argument("--max-weight", type=float, default=8.0)
    p.add_argument("--temperature", type=float, default=1.0)
    p.add_argument("--top-groups", type=int, default=12)
    p.add_argument("--exact-command", default="")
    p.add_argument("--output-receipt")

    p = sub.add_parser("acquisition-plan")
    p.add_argument("db")
    p.add_argument("--schedule-receipt", required=True)
    p.add_argument("--manifest-csv", default="benchmark/manifest.csv")
    p.add_argument("--target-hours", type=float, default=10.0)
    p.add_argument("--limit", type=int, default=8)
    p.add_argument("--output-receipt")

    p = sub.add_parser("acquisition-intake")
    p.add_argument("candidates_jsonl")
    p.add_argument("--acquisition-plan", required=True)
    p.add_argument("--manifest-csv", default="benchmark/manifest.csv")
    p.add_argument("--output-receipt")

    p = sub.add_parser("quality-cards")
    p.add_argument("heldout_jsonl")
    p.add_argument("--metrics-json", required=True)
    p.add_argument("--manifest-csv")
    p.add_argument("--output-dir", required=True)
    p.add_argument("--model-name", required=True)
    p.add_argument("--release-decision")
    p.add_argument("--release-decision-json")
    p.add_argument("--receipt-path")
    p.add_argument("--card-id", default="quality_card")
    p.add_argument("--group-key", default="accent_family")
    p.add_argument("--per-group-key", default="by_accent_family")
    p.add_argument("--limit-per-group", type=int, default=5)
    p.add_argument("--score-key", default="wer")
    p.add_argument("--reference-key", default="reference")
    p.add_argument("--hypothesis-key", default="hypothesis")

    p = sub.add_parser("repair-quality-cards")
    p.add_argument("repair_jsonl")
    p.add_argument("--output-dir", required=True)
    p.add_argument("--model-name", required=True)
    p.add_argument("--release-decision")
    p.add_argument("--release-decision-json")
    p.add_argument("--receipt-path")
    p.add_argument("--output-receipt")
    p.add_argument("--card-id", default="repair_quality_card")
    p.add_argument("--group-key", default="accent_family")
    p.add_argument("--reference-key", default="reference_clean")
    p.add_argument("--hypothesis-key", default="hypothesis_clean")
    p.add_argument("--limit-per-group", type=int, default=5)
    p.add_argument("--split", default="synthetic repair seed")
    p.add_argument("--license-summary", default="text-only synthetic/illustrative repair eval; no licensed audio")

    p = sub.add_parser("ledger-stats")
    p.add_argument("db")

    p = sub.add_parser("split-leaks")
    p.add_argument("db")

    p = sub.add_parser("audit")
    p.add_argument("db")
    p.add_argument("--metrics-json")

    p = sub.add_parser("benchmark-freeze")
    p.add_argument("--manifest-csv", default="benchmark/manifest.csv")
    p.add_argument("--scorer-py", default="benchmark/score.py")
    p.add_argument("--governance-md", default="benchmark/GOVERNANCE.md")
    p.add_argument("--losses-md", default="benchmark/babel_loses_here.md")
    p.add_argument("--low-n-threshold", type=int, default=5)
    p.add_argument("--output-receipt")

    p = sub.add_parser("compute-preflight")
    p.add_argument("db")
    p.add_argument("--workspace", default=".")
    p.add_argument("--component", default="acoustic_distillation")
    p.add_argument("--min-free-gb", type=float, default=60.0)
    p.add_argument("--metrics-json")
    p.add_argument("--require-phase-check", action="append", default=[])
    p.add_argument("--require-experiments", type=int, default=1)
    p.add_argument("--require-receipt", action="append", default=[])
    p.add_argument("--output-receipt")

    p = sub.add_parser("studio-distillation-plan")
    p.add_argument("db")
    p.add_argument("--metrics-json", required=True)
    p.add_argument("--preflight-receipt", required=True)
    p.add_argument("--worst-cell-plan", required=True)
    p.add_argument("--previous-json")
    p.add_argument("--manifest-csv", default="benchmark/manifest.csv")
    p.add_argument("--target-profile", default="mac_studio_m1_ultra_128gb")
    p.add_argument("--host-profile", default="pre_studio_verifier")
    p.add_argument("--teacher", default="openai/whisper-large-v3-turbo")
    p.add_argument("--student", default="openai/whisper-tiny")
    p.add_argument("--seeds", default="13,29,47")
    p.add_argument("--top-cells", type=int, default=4)
    p.add_argument("--epochs", type=int, default=3)
    p.add_argument("--batch-size", type=int, default=4)
    p.add_argument("--lr", type=float, default=3e-6)
    p.add_argument("--encoder-lr", type=float, default=1e-6)
    p.add_argument("--eval-limit", type=int, default=0)
    p.add_argument("--output-receipt")

    p = sub.add_parser("assign-splits")
    p.add_argument("db")
    p.add_argument("--train", type=float, default=0.8)
    p.add_argument("--dev", type=float, default=0.1)
    p.add_argument("--test", type=float, default=0.1)
    p.add_argument("--group-key", default="auto")
    p.add_argument("--salt", default="babel")
    p.add_argument("--overwrite", action="store_true")

    p = sub.add_parser("repair-hygiene")
    p.add_argument("db")
    p.add_argument("--split", default="repair_train")
    p.add_argument("--source-prefix", default="synthetic-repair")

    p = sub.add_parser("export-shard")
    p.add_argument("db")
    p.add_argument("--split")
    p.add_argument("--training-allowed", action="store_true")
    p.add_argument("--eval-allowed", action="store_true")
    p.add_argument("--limit", type=int)

    p = sub.add_parser("review-queue")
    p.add_argument("db")
    p.add_argument("--limit", type=int, default=20)

    p = sub.add_parser("eval-asr")
    p.add_argument("jsonl")
    p.add_argument("--group-key", default="accent_family")
    p.add_argument("--reference-key", default="reference")
    p.add_argument("--hypothesis-key", default="hypothesis")

    p = sub.add_parser("local-eval")
    p.add_argument("--model", required=True, help="HF id or local checkpoint dir")
    p.add_argument("--tag")
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--device")

    p = sub.add_parser("error-report")
    p.add_argument("--baseline-jsonl", default="eval/baseline/turbo_baseline.held_out.jsonl")
    p.add_argument("--clips-jsonl", default="archive/held_out_clips.jsonl")
    p.add_argument("--output-json", default="eval/baseline/turbo_error_report.json")
    p.add_argument("--output-md", default="eval/baseline/turbo_error_report.md")

    p = sub.add_parser("prepare-tail-shards")
    p.add_argument("--src")
    p.add_argument("--dst")
    p.add_argument("--output-manifest")
    p.add_argument("--keep-newest", action="store_true")

    p = sub.add_parser("tail-audit")
    p.add_argument("--shards")
    p.add_argument("--clips")
    p.add_argument("--transcripts")
    p.add_argument("--out")
    p.add_argument("--workers", type=int, default=0)
    p.add_argument("--limit-shards", type=int, default=0)
    p.add_argument("--max-clips-per-shard", type=int, default=0)

    p = sub.add_parser("eval-nbest")
    p.add_argument("jsonl")
    p.add_argument("--group-key", default="accent_family")

    p = sub.add_parser("eval-repair")
    p.add_argument("jsonl")
    p.add_argument("--group-key", default="accent_family")

    p = sub.add_parser("eval-segmentation")
    p.add_argument("jsonl")
    p.add_argument("--group-key", default="accent_family")
    p.add_argument("--tolerance", type=int, default=0)

    p = sub.add_parser("release-gate")
    p.add_argument("current_json")
    p.add_argument("--previous-json")

    p = sub.add_parser("scorecard")
    p.add_argument("tiers_json")
    p.add_argument("--previous-json")

    p = sub.add_parser("phase-status")
    p.add_argument("db")
    p.add_argument("--metrics-json")

    p = sub.add_parser("report")
    p.add_argument("db")
    p.add_argument("--metrics-json")
    p.add_argument("--targets-json")

    p = sub.add_parser("run-cycle")
    p.add_argument("db")
    p.add_argument("metrics_json")
    p.add_argument("--experiment-id", required=True)
    p.add_argument("--exact-command", required=True)
    p.add_argument("--component", required=True)
    p.add_argument("--hypothesis", required=True)
    p.add_argument("--split", required=True)
    p.add_argument("--license-summary")
    p.add_argument("--license-summary-json")
    p.add_argument("--previous-json")
    p.add_argument("--heldout-jsonl")
    p.add_argument("--output-receipt")
    p.add_argument("--per-group-key", default="by_accent_family")
    p.add_argument("--reference-key", default="reference")
    p.add_argument("--hypothesis-key", default="hypothesis")
    p.add_argument("--score-key", default="wer")
    p.add_argument("--decision")
    p.add_argument("--notes", default="")
    p.add_argument("--created-at")

    p = sub.add_parser("experiment-record")
    p.add_argument("db")
    p.add_argument("experiment_json")

    p = sub.add_parser("experiments")
    p.add_argument("db")
    p.add_argument("--limit", type=int, default=20)

    args = parser.parse_args(argv)
    if args.cmd == "validate-stage":
        emit(validate_stage(load_json(args.json_file), args.stage))
    elif args.cmd == "validate-dir":
        result = validate_dir(args.dir)
        emit(result)
        return 0 if result["passed"] == result["checked"] else 1
    elif args.cmd == "validate-receipts":
        result = validate_experiment_receipts(args.receipts)
        if args.output_json:
            path = Path(args.output_json)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        emit(result)
        return 0 if result["passed"] else 1
    elif args.cmd == "route":
        emit({"route": route_stage_a(validate_stage(load_json(args.stage_a_json), "stage_a"))})
    elif args.cmd == "inspect-wav":
        emit(inspect_wav(args.wav_file))
    elif args.cmd == "manifest-wavs":
        rows = manifest_wavs(
            args.root,
            source_type=args.source_type,
            license_name=args.license_name,
            license_url=args.license_url,
            training_allowed=args.training_allowed,
            eval_allowed=args.eval_allowed,
        )
        if args.db:
            emit({"manifested": len(rows), "upserted": upsert_clips(args.db, rows)})
        else:
            emit(rows)
    elif args.cmd == "ledger-init":
        emit({"db": str(init_ledger(args.db))})
    elif args.cmd == "ledger-upsert":
        emit({"upserted": upsert_clips(args.db, iter_jsonl(args.jsonl))})
    elif args.cmd == "coverage":
        emit(coverage(args.db, args.dims))
    elif args.cmd == "coverage-gaps":
        emit(coverage_gaps(args.db, load_json(args.targets_json)))
    elif args.cmd == "worst-cell-plan":
        emit(
            worst_cell_plan(
                args.db,
                load_json(args.metrics_json),
                group_key=args.group_key,
                per_group_key=args.per_group_key,
                target_hours=args.target_hours,
                target_eval_clips=args.target_eval_clips,
                limit=args.limit,
            )
        )
    elif args.cmd == "group-dro-schedule":
        emit(
            group_dro_schedule(
                args.db,
                metrics=load_json(args.metrics_json),
                worst_cell_plan_receipt=args.worst_cell_plan,
                studio_plan_receipt=args.studio_plan,
                group_key=args.group_key,
                per_group_key=args.per_group_key,
                target_hours=args.target_hours,
                target_eval_clips=args.target_eval_clips,
                max_weight=args.max_weight,
                temperature=args.temperature,
                top_groups=args.top_groups,
                exact_command=args.exact_command,
                output_receipt=args.output_receipt,
            )
        )
    elif args.cmd == "acquisition-plan":
        emit(
            acquisition_plan(
                args.db,
                schedule_receipt=args.schedule_receipt,
                manifest_csv=args.manifest_csv,
                target_hours=args.target_hours,
                limit=args.limit,
                output_receipt=args.output_receipt,
            )
        )
    elif args.cmd == "acquisition-intake":
        result = validate_acquisition_intake(
            iter_jsonl(args.candidates_jsonl),
            acquisition_plan_receipt=args.acquisition_plan,
            manifest_csv=args.manifest_csv,
            output_receipt=args.output_receipt,
        )
        emit(result)
        return 0 if result["passed"] else 1
    elif args.cmd == "quality-cards":
        if args.release_decision_json:
            release_decision = load_json(args.release_decision_json)
        elif args.release_decision:
            release_decision = args.release_decision
        else:
            parser.error("quality-cards requires --release-decision or --release-decision-json")
        emit(
            quality_cards(
                iter_jsonl(args.heldout_jsonl),
                load_json(args.metrics_json),
                output_dir=args.output_dir,
                model_name=args.model_name,
                release_decision=release_decision,
                manifest_rows=load_csv_rows(args.manifest_csv) if args.manifest_csv else (),
                receipt_path=args.receipt_path,
                card_id=args.card_id,
                group_key=args.group_key,
                per_group_key=args.per_group_key,
                limit_per_group=args.limit_per_group,
                score_key=args.score_key,
                reference_key=args.reference_key,
                hypothesis_key=args.hypothesis_key,
            )
        )
    elif args.cmd == "repair-quality-cards":
        if args.release_decision_json:
            release_decision = load_json(args.release_decision_json)
        elif args.release_decision:
            release_decision = args.release_decision
        else:
            parser.error("repair-quality-cards requires --release-decision or --release-decision-json")
        emit(
            repair_quality_cards(
                iter_jsonl(args.repair_jsonl),
                output_dir=args.output_dir,
                model_name=args.model_name,
                release_decision=release_decision,
                receipt_path=args.receipt_path,
                output_receipt=args.output_receipt,
                card_id=args.card_id,
                group_key=args.group_key,
                reference_key=args.reference_key,
                hypothesis_key=args.hypothesis_key,
                limit_per_group=args.limit_per_group,
                split=args.split,
                license_summary=args.license_summary,
            )
        )
    elif args.cmd == "ledger-stats":
        emit(ledger_stats(args.db))
    elif args.cmd == "split-leaks":
        emit(split_leaks(args.db))
    elif args.cmd == "audit":
        metrics = load_json(args.metrics_json) if args.metrics_json else None
        emit(audit(args.db, metrics))
    elif args.cmd == "benchmark-freeze":
        emit(
            benchmark_freeze(
                manifest_csv=args.manifest_csv,
                scorer_py=args.scorer_py,
                governance_md=args.governance_md,
                losses_md=args.losses_md,
                low_n_threshold=args.low_n_threshold,
                output_receipt=args.output_receipt,
            )
        )
    elif args.cmd == "compute-preflight":
        metrics = load_json(args.metrics_json) if args.metrics_json else None
        required = tuple(args.require_phase_check) if args.require_phase_check else (
            "phase_0_contract_loop",
            "phase_1_eval_seed",
            "phase_1_repair_gate",
            "phase_2_data_gate",
            "license_gate",
            "defect_gate",
            "split_gate",
            "runpod_ready",
        )
        result = compute_preflight(
            args.db,
            workspace=args.workspace,
            component=args.component,
            min_free_gb=args.min_free_gb,
            metrics=metrics,
            required_phase_checks=required,
            require_experiments=args.require_experiments,
            require_receipts=args.require_receipt,
            output_receipt=args.output_receipt,
        )
        emit(result)
        return 0 if result["passed"] else 1
    elif args.cmd == "studio-distillation-plan":
        seeds = tuple(int(part.strip()) for part in args.seeds.split(",") if part.strip())
        emit(
            studio_distillation_plan(
                args.db,
                metrics=load_json(args.metrics_json),
                preflight_receipt=args.preflight_receipt,
                worst_cell_plan_receipt=args.worst_cell_plan,
                previous_metrics=load_json(args.previous_json) if args.previous_json else None,
                manifest_csv=args.manifest_csv,
                target_profile=args.target_profile,
                host_profile=args.host_profile,
                teacher=args.teacher,
                student=args.student,
                seeds=seeds,
                top_cells=args.top_cells,
                epochs=args.epochs,
                batch_size=args.batch_size,
                lr=args.lr,
                encoder_lr=args.encoder_lr,
                eval_limit=args.eval_limit,
                output_receipt=args.output_receipt,
            )
        )
    elif args.cmd == "assign-splits":
        emit(
            assign_splits(
                args.db,
                train=args.train,
                dev=args.dev,
                test=args.test,
                group_key=args.group_key,
                salt=args.salt,
                overwrite=args.overwrite,
            )
        )
    elif args.cmd == "repair-hygiene":
        emit(repair_hygiene(args.db, split=args.split, source_prefix=args.source_prefix))
    elif args.cmd == "export-shard":
        emit(
            export_shard(
                args.db,
                split=args.split,
                training_allowed=True if args.training_allowed else None,
                eval_allowed=True if args.eval_allowed else None,
                limit=args.limit,
            )
        )
    elif args.cmd == "review-queue":
        emit(review_queue(args.db, args.limit))
    elif args.cmd == "eval-asr":
        emit(
            eval_asr(
                iter_jsonl(args.jsonl),
                group_key=args.group_key,
                reference_key=args.reference_key,
                hypothesis_key=args.hypothesis_key,
            )
        )
    elif args.cmd == "local-eval":
        from .local_eval import run_local_eval

        return run_local_eval(
            model_path=args.model,
            tag=args.tag,
            limit=args.limit,
            device=args.device,
        )
    elif args.cmd == "error-report":
        from .error_report import write_error_report

        result = write_error_report(
            baseline_jsonl=args.baseline_jsonl,
            clips_jsonl=args.clips_jsonl,
            output_json=args.output_json,
            output_md=args.output_md,
        )
        emit({"output_json": result["output_json"], "output_md": result["output_md"]})
    elif args.cmd == "prepare-tail-shards":
        from .tail_shards import prepare_tail_shards

        emit(
            prepare_tail_shards(
                src=args.src,
                dst=args.dst,
                output_manifest=args.output_manifest,
                keep_newest=args.keep_newest,
            )
        )
    elif args.cmd == "tail-audit":
        from .tail_audit import run_tail_audit

        emit(
            run_tail_audit(
                shards=args.shards,
                clips=args.clips,
                transcripts=args.transcripts,
                out=args.out,
                workers=args.workers or None,
                limit_shards=args.limit_shards,
                max_clips_per_shard=args.max_clips_per_shard,
            )
        )
    elif args.cmd == "eval-nbest":
        emit(eval_nbest(iter_jsonl(args.jsonl), group_key=args.group_key))
    elif args.cmd == "eval-repair":
        emit(eval_repair(iter_jsonl(args.jsonl), group_key=args.group_key))
    elif args.cmd == "eval-segmentation":
        emit(eval_segmentation(iter_jsonl(args.jsonl), group_key=args.group_key, tolerance=args.tolerance))
    elif args.cmd == "release-gate":
        previous = load_json(args.previous_json) if args.previous_json else None
        emit(release_gate(load_json(args.current_json), previous))
    elif args.cmd == "scorecard":
        previous = load_json(args.previous_json) if args.previous_json else None
        result = scorecard(load_json(args.tiers_json), previous)
        print(result["table"])
        if result["gate"]:
            status = "passed" if result["gate"]["passed"] else "failed"
            print(f"\nrelease-gate vs previous flagship: {status}")
            for failure in result["gate"]["failures"]:
                print(f"- {failure}")
            return 0 if result["gate"]["passed"] else 1
    elif args.cmd == "phase-status":
        metrics = load_json(args.metrics_json) if args.metrics_json else None
        emit(phase_status(args.db, metrics))
    elif args.cmd == "report":
        metrics = load_json(args.metrics_json) if args.metrics_json else None
        targets = load_json(args.targets_json) if args.targets_json else None
        print(markdown_report(args.db, metrics=metrics, targets=targets))
    elif args.cmd == "run-cycle":
        if args.license_summary_json:
            license_summary = load_json(args.license_summary_json)
        elif args.license_summary:
            license_summary = {"summary": args.license_summary}
        else:
            parser.error("run-cycle requires --license-summary or --license-summary-json")
        heldout = list(iter_jsonl(args.heldout_jsonl)) if args.heldout_jsonl else None
        previous = load_json(args.previous_json) if args.previous_json else None
        emit(
            run_cycle_receipt(
                args.db,
                experiment_id=args.experiment_id,
                metrics=load_json(args.metrics_json),
                exact_command=args.exact_command,
                component=args.component,
                hypothesis=args.hypothesis,
                split=args.split,
                license_summary=license_summary,
                previous_metrics=previous,
                heldout_rows=heldout,
                per_group_key=args.per_group_key,
                reference_key=args.reference_key,
                hypothesis_key=args.hypothesis_key,
                score_key=args.score_key,
                decision=args.decision,
                notes=args.notes,
                commit=git_commit(),
                workspace_dirty=git_dirty(),
                output_receipt=args.output_receipt,
                created_at=args.created_at,
            )
        )
    elif args.cmd == "experiment-record":
        row = load_json(args.experiment_json)
        record_experiment(args.db, **row)
        emit({"recorded": row["experiment_id"]})
    elif args.cmd == "experiments":
        emit(experiments(args.db, args.limit))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
