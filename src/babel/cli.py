from __future__ import annotations

import argparse
import json
from typing import Any

from .core import (
    assign_splits,
    audit,
    coverage_gaps,
    coverage,
    eval_asr,
    eval_nbest,
    eval_repair,
    eval_segmentation,
    export_shard,
    experiments,
    inspect_wav,
    init_ledger,
    iter_jsonl,
    ledger_stats,
    load_json,
    markdown_report,
    manifest_wavs,
    phase_status,
    record_experiment,
    release_gate,
    review_queue,
    route_stage_a,
    scorecard,
    split_leaks,
    upsert_clips,
    validate_dir,
    validate_stage,
)


def emit(value: Any) -> None:
    print(json.dumps(value, indent=2, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="babel")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("validate-stage")
    p.add_argument("stage", choices=("stage_a", "stage_a5", "stage_b"))
    p.add_argument("json_file")

    p = sub.add_parser("validate-dir")
    p.add_argument("dir")

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

    p = sub.add_parser("ledger-stats")
    p.add_argument("db")

    p = sub.add_parser("split-leaks")
    p.add_argument("db")

    p = sub.add_parser("audit")
    p.add_argument("db")
    p.add_argument("--metrics-json")

    p = sub.add_parser("assign-splits")
    p.add_argument("db")
    p.add_argument("--train", type=float, default=0.8)
    p.add_argument("--dev", type=float, default=0.1)
    p.add_argument("--test", type=float, default=0.1)
    p.add_argument("--group-key", default="auto")
    p.add_argument("--salt", default="babel")
    p.add_argument("--overwrite", action="store_true")

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
    elif args.cmd == "ledger-stats":
        emit(ledger_stats(args.db))
    elif args.cmd == "split-leaks":
        emit(split_leaks(args.db))
    elif args.cmd == "audit":
        metrics = load_json(args.metrics_json) if args.metrics_json else None
        emit(audit(args.db, metrics))
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
    elif args.cmd == "experiment-record":
        row = load_json(args.experiment_json)
        record_experiment(args.db, **row)
        emit({"recorded": row["experiment_id"]})
    elif args.cmd == "experiments":
        emit(experiments(args.db, args.limit))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
