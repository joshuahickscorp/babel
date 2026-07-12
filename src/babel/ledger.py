from __future__ import annotations

import csv
import json
import math
import sqlite3
from collections.abc import Mapping, Sequence
from contextlib import closing
from pathlib import Path
from typing import Any

CLIP_COLUMNS = {
    "clip_id": "text primary key",
    "source_id": "text",
    "source_url": "text",
    "source_type": "text",
    "license_name": "text",
    "license_url": "text",
    "attribution": "text",
    "redistribution_allowed": "integer",
    "training_allowed": "integer",
    "eval_allowed": "integer",
    "duration_s": "real",
    "sample_rate_hz": "integer",
    "audio_hash": "text",
    "speaker_hash": "text",
    "split": "text",
    "transcript_type": "text",
    "transcript_confidence": "real",
    "teacher_agreement": "real",
    "accent_family": "text",
    "accent_confidence": "real",
    "l1_hint": "text",
    "fluency_tier": "text",
    "noise_tier": "text",
    "register": "text",
    "language_mix": "text",
    "cell_rarity": "real",
    "human_review_priority": "real",
    "pii_status": "text",
    "notes": "text",
}

EXPERIMENT_COLUMNS = {
    "experiment_id": "text primary key",
    "created_at": "text default current_timestamp",
    "hypothesis": "text",
    "component": "text",
    "data": "text",
    "metrics_json": "text",
    "decision": "text",
    "notes": "text",
}


def init_ledger(path: str | Path) -> Path:
    db_path = Path(path)
    columns = ", ".join(f"{name} {kind}" for name, kind in CLIP_COLUMNS.items())
    experiment_columns = ", ".join(f"{name} {kind}" for name, kind in EXPERIMENT_COLUMNS.items())
    with closing(sqlite3.connect(db_path)) as db, db:
        db.execute(f"create table if not exists clips ({columns})")
        db.execute(f"create table if not exists experiments ({experiment_columns})")
        db.execute("create index if not exists idx_clips_cell on clips(accent_family, fluency_tier, noise_tier)")
        db.execute("create index if not exists idx_clips_split on clips(split)")
    return db_path


def upsert_clip(path: str | Path, **row: Any) -> None:
    unknown = set(row) - set(CLIP_COLUMNS)
    if unknown:
        raise ValueError(f"unknown ledger fields: {', '.join(sorted(unknown))}")
    if "clip_id" not in row:
        raise ValueError("clip_id is required")
    init_ledger(path)
    names = list(row)
    placeholders = ", ".join("?" for _ in names)
    updates = ", ".join(f"{name}=excluded.{name}" for name in names if name != "clip_id")
    conflict = f"do update set {updates}" if updates else "do nothing"
    sql = (
        f"insert into clips ({', '.join(names)}) values ({placeholders}) "
        f"on conflict(clip_id) {conflict}"
    )
    with closing(sqlite3.connect(path)) as db, db:
        db.execute(sql, [row[name] for name in names])


def upsert_clips(path: str | Path, rows: Sequence[Mapping[str, Any]]) -> int:
    # ONE connection + one transaction + executemany per column-signature. The old per-row loop opened a
    # fresh connection + init_ledger + commit for EVERY row (~240 rows/s) and stalled for hours on the
    # network (fuseblk) volume for the 1M-row cycle upserts -- the exact hang we must not hit unattended.
    rows = [dict(r) for r in rows]
    if not rows:
        return 0
    for r in rows:                                            # same validation as upsert_clip()
        if "clip_id" not in r:
            raise ValueError("clip_id is required")
        unknown = set(r) - set(CLIP_COLUMNS)
        if unknown:
            raise ValueError(f"unknown ledger fields: {', '.join(sorted(unknown))}")
    init_ledger(path)
    groups: dict[tuple, list] = {}                            # group by present-column set for executemany
    for r in rows:
        names = tuple(r)
        groups.setdefault(names, []).append([r[n] for n in names])
    n = 0
    with closing(sqlite3.connect(path)) as db:
        db.execute("pragma synchronous=off")                 # ledger is rebuildable; trade durability for
        db.execute("pragma journal_mode=memory")             # speed so a 1M-row commit doesn't crawl on FUSE
        with db:
            for names, batch in groups.items():
                placeholders = ", ".join("?" for _ in names)
                updates = ", ".join(f"{nm}=excluded.{nm}" for nm in names if nm != "clip_id")
                conflict = f"do update set {updates}" if updates else "do nothing"
                sql = (f"insert into clips ({', '.join(names)}) values ({placeholders}) "
                       f"on conflict(clip_id) {conflict}")
                db.executemany(sql, batch)
                n += len(batch)
    return n


def coverage(path: str | Path, dims: Sequence[str] = ("accent_family", "fluency_tier", "noise_tier")) -> list[dict[str, Any]]:
    bad = set(dims) - set(CLIP_COLUMNS)
    if bad:
        raise ValueError(f"unknown coverage dimensions: {', '.join(sorted(bad))}")
    select = ", ".join(dims)
    sql = f"select {select}, count(*), coalesce(sum(duration_s), 0) / 3600 from clips group by {select}"
    with closing(sqlite3.connect(path)) as db:
        rows = db.execute(sql).fetchall()
    return [dict(zip((*dims, "clips", "hours"), row, strict=True)) for row in rows]


def coverage_entropy(
    path: str | Path,
    dims: Sequence[str] = ("accent_family", "fluency_tier", "noise_tier"),
) -> float:
    init_ledger(path)
    weights = [row["hours"] for row in coverage(path, dims) if row["hours"] > 0]
    total = sum(weights)
    if total <= 0 or len(weights) <= 1:
        return 0.0
    probs = [weight / total for weight in weights]
    return -sum(p * math.log(p) for p in probs) / math.log(len(weights))


def ledger_stats(path: str | Path) -> dict[str, Any]:
    init_ledger(path)
    with closing(sqlite3.connect(path)) as db:
        total_clips = db.execute("select count(*) from clips").fetchone()[0]
        train_hours = db.execute(
            "select coalesce(sum(duration_s), 0) / 3600 from clips where coalesce(training_allowed, 0) = 1"
        ).fetchone()[0]
        eval_clips = db.execute("select count(*) from clips where coalesce(eval_allowed, 0) = 1").fetchone()[0]
        coverage_cells = db.execute(
            """
            select count(*) from (
                select accent_family, fluency_tier, noise_tier
                from clips
                group by accent_family, fluency_tier, noise_tier
            )
            """
        ).fetchone()[0]
        experiments_count = db.execute("select count(*) from experiments").fetchone()[0]
    return {
        "clips": total_clips,
        "train_hours": train_hours,
        "eval_clips": eval_clips,
        "coverage_cells": coverage_cells,
        "coverage_entropy": coverage_entropy(path),
        "experiments": experiments_count,
    }


def coverage_gaps(
    path: str | Path,
    targets: Sequence[Mapping[str, Any]],
    *,
    dims: Sequence[str] = ("accent_family", "fluency_tier", "noise_tier"),
) -> list[dict[str, Any]]:
    have = {tuple(row.get(dim) for dim in dims): row["hours"] for row in coverage(path, dims)}
    gaps = []
    for target in targets:
        key = tuple(target.get(dim) for dim in dims)
        target_hours = float(target.get("target_hours", 0))
        current_hours = have.get(key, 0.0)
        if current_hours < target_hours:
            gaps.append(
                {
                    **{dim: target.get(dim) for dim in dims},
                    "hours": current_hours,
                    "gap_hours": target_hours - current_hours,
                }
            )
    return sorted(gaps, key=lambda row: row["gap_hours"], reverse=True)


def worst_cell_plan(
    path: str | Path,
    metrics: Mapping[str, Any],
    *,
    group_key: str = "accent_family",
    per_group_key: str = "by_accent_family",
    target_hours: float = 10.0,
    target_eval_clips: int = 10,
    limit: int = 20,
) -> list[dict[str, Any]]:
    if group_key not in CLIP_COLUMNS:
        raise ValueError(f"unknown group key: {group_key}")
    if target_hours < 0:
        raise ValueError("target_hours must be non-negative")
    if target_eval_clips < 0:
        raise ValueError("target_eval_clips must be non-negative")
    per_group = metrics.get(per_group_key)
    if not isinstance(per_group, Mapping) or not per_group:
        raise ValueError(f"metrics missing per-group table: {per_group_key}")
    init_ledger(path)
    sql = f"""
        select
            coalesce({group_key}, 'unknown') as group_value,
            sum(case when coalesce(training_allowed, 0) = 1 then 1 else 0 end) as train_clips,
            coalesce(sum(case when coalesce(training_allowed, 0) = 1 then duration_s else 0 end), 0)
                / 3600.0 as train_hours,
            sum(case when coalesce(eval_allowed, 0) = 1 then 1 else 0 end) as eval_clips
        from clips
        group by coalesce({group_key}, 'unknown')
    """
    with closing(sqlite3.connect(path)) as db:
        db.row_factory = sqlite3.Row
        coverage_by_group = {row["group_value"]: dict(row) for row in db.execute(sql)}
    rows = []
    for group, raw_score in per_group.items():
        score = float(raw_score)
        cov = coverage_by_group.get(str(group), {})
        train_hours = float(cov.get("train_hours") or 0.0)
        train_clips = int(cov.get("train_clips") or 0)
        eval_clips = int(cov.get("eval_clips") or 0)
        gap_hours = max(0.0, target_hours - train_hours)
        eval_gap = max(0, target_eval_clips - eval_clips)
        hours_factor = (gap_hours / target_hours) if target_hours else 0.0
        eval_factor = (eval_gap / target_eval_clips) if target_eval_clips else 0.0
        priority = score * (1.0 + hours_factor + eval_factor)
        if gap_hours > 0:
            action = "acquire_or_license_training_audio"
        elif eval_gap > 0:
            action = "add_or_score_held_out_eval"
        else:
            action = "run_group_dro_or_failure_review"
        rows.append(
            {
                group_key: group,
                "group_metric": score,
                "train_hours": round(train_hours, 4),
                "train_clips": train_clips,
                "eval_clips": eval_clips,
                "target_hours": target_hours,
                "gap_hours": round(gap_hours, 4),
                "target_eval_clips": target_eval_clips,
                "eval_gap": eval_gap,
                "priority": round(priority, 6),
                "recommended_action": action,
            }
        )
    rows.sort(key=lambda row: (row["priority"], row["group_metric"], row["gap_hours"]), reverse=True)
    return [{**row, "rank": i + 1} for i, row in enumerate(rows[:limit])]


def load_csv_rows(path: str | Path) -> list[dict[str, Any]]:
    with Path(path).open(newline="") as file:
        return [dict(row) for row in csv.DictReader(file)]


def split_leaks(path: str | Path) -> list[dict[str, Any]]:
    sql = """
        select kind, value, group_concat(distinct split) as splits
        from (
            select 'audio_hash' as kind, audio_hash as value, split from clips where audio_hash is not null and split is not null
            union all
            select 'speaker_hash' as kind, speaker_hash as value, split from clips where speaker_hash is not null and split is not null
            union all
            select 'source_id' as kind, source_id as value, split from clips where source_id is not null and split is not null
        )
        group by kind, value
        having count(distinct split) > 1
    """
    init_ledger(path)
    with closing(sqlite3.connect(path)) as db:
        db.row_factory = sqlite3.Row
        return [dict(row) for row in db.execute(sql).fetchall()]


def review_queue(path: str | Path, limit: int = 20) -> list[dict[str, Any]]:
    sql = """
        select clip_id, source_id, accent_family, fluency_tier, noise_tier,
               teacher_agreement, cell_rarity, human_review_priority, notes
        from clips
        where coalesce(training_allowed, 0) = 1 or coalesce(eval_allowed, 0) = 1
        order by
            coalesce(human_review_priority, 0) desc,
            coalesce(cell_rarity, 0) desc,
            coalesce(teacher_agreement, 1) asc
        limit ?
    """
    with closing(sqlite3.connect(path)) as db:
        db.row_factory = sqlite3.Row
        return [dict(row) for row in db.execute(sql, [limit]).fetchall()]


def record_experiment(path: str | Path, **row: Any) -> None:
    unknown = set(row) - set(EXPERIMENT_COLUMNS)
    if unknown:
        raise ValueError(f"unknown experiment fields: {', '.join(sorted(unknown))}")
    if "experiment_id" not in row:
        raise ValueError("experiment_id is required")
    if "metrics_json" in row and not isinstance(row["metrics_json"], str):
        row["metrics_json"] = json.dumps(row["metrics_json"], sort_keys=True)
    init_ledger(path)
    names = list(row)
    placeholders = ", ".join("?" for _ in names)
    updates = ", ".join(f"{name}=excluded.{name}" for name in names if name != "experiment_id")
    conflict = f"do update set {updates}" if updates else "do nothing"
    sql = (
        f"insert into experiments ({', '.join(names)}) values ({placeholders}) "
        f"on conflict(experiment_id) {conflict}"
    )
    with closing(sqlite3.connect(path)) as db, db:
        db.execute(sql, [row[name] for name in names])


def experiments(path: str | Path, limit: int = 20) -> list[dict[str, Any]]:
    sql = """
        select experiment_id, created_at, hypothesis, component, data, metrics_json, decision, notes
        from experiments
        order by created_at desc, experiment_id desc
        limit ?
    """
    with closing(sqlite3.connect(path)) as db:
        db.row_factory = sqlite3.Row
        rows = [dict(row) for row in db.execute(sql, [limit]).fetchall()]
    for row in rows:
        if row.get("metrics_json"):
            row["metrics"] = json.loads(row.pop("metrics_json"))
    return rows
