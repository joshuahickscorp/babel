from __future__ import annotations

import hashlib
import sqlite3
from collections.abc import Mapping
from contextlib import closing
from pathlib import Path
from typing import Any

from .ledger import CLIP_COLUMNS, init_ledger


def stable_bucket(value: str, *, salt: str = "babel") -> float:
    digest = hashlib.sha256(f"{salt}:{value}".encode()).hexdigest()[:16]
    return int(digest, 16) / float(16**16)


def assign_splits(
    path: str | Path,
    *,
    train: float = 0.8,
    dev: float = 0.1,
    test: float = 0.1,
    group_key: str = "auto",
    salt: str = "babel",
    overwrite: bool = False,
) -> dict[str, int]:
    if abs((train + dev + test) - 1.0) > 1e-9:
        raise ValueError("train + dev + test must equal 1")
    fields = ("clip_id", "speaker_hash", "source_id", "audio_hash", "split", "training_allowed", "eval_allowed")
    if group_key != "auto" and group_key not in CLIP_COLUMNS:
        raise ValueError(f"unknown split group key: {group_key}")
    init_ledger(path)
    with closing(sqlite3.connect(path)) as db, db:
        db.row_factory = sqlite3.Row
        rows = [dict(row) for row in db.execute(f"select {', '.join(fields)} from clips").fetchall()]
        counts = {"train": 0, "dev": 0, "test": 0, "skipped": 0}
        for row in rows:
            old_split = row.get("split")
            eligible = row.get("training_allowed") or row.get("eval_allowed")
            if not eligible or old_split == "quarantine" or (old_split not in (None, "", "unassigned") and not overwrite):
                counts["skipped"] += 1
                continue
            group = _split_group(row, group_key)
            bucket = stable_bucket(group, salt=salt)
            split = "train" if bucket < train else "dev" if bucket < train + dev else "test"
            db.execute("update clips set split = ? where clip_id = ?", [split, row["clip_id"]])
            counts[split] += 1
    return counts


def _split_group(row: Mapping[str, Any], group_key: str) -> str:
    if group_key != "auto":
        return str(row.get(group_key) or row["clip_id"])
    for key in ("speaker_hash", "source_id", "audio_hash", "clip_id"):
        if row.get(key):
            return str(row[key])
    return str(row["clip_id"])


def repair_hygiene(
    path: str | Path,
    *,
    split: str = "repair_train",
    source_prefix: str = "synthetic-repair",
) -> dict[str, int | str]:
    if not split:
        raise ValueError("split is required")
    if not source_prefix:
        raise ValueError("source_prefix is required")
    init_ledger(path)
    where = """
        source_type = 'synthetic'
        and transcript_type = 'synthetic'
        and notes like 'repair;%'
        and (
            split is null or split = '' or split = 'unassigned'
            or source_id is null or source_id = ''
            or redistribution_allowed is null
        )
    """
    with closing(sqlite3.connect(path)) as db, db:
        db.row_factory = sqlite3.Row
        before = dict(
            db.execute(
                f"""
                select
                    count(*) as matched,
                    sum(case when split is null or split = '' or split = 'unassigned' then 1 else 0 end)
                        as split_missing,
                    sum(case when source_id is null or source_id = '' then 1 else 0 end)
                        as source_missing,
                    sum(case when redistribution_allowed is null then 1 else 0 end)
                        as redistribution_missing
                from clips
                where {where}
                """
            ).fetchone()
        )
        db.execute(
            f"""
            update clips
            set split = case
                    when split is null or split = '' or split = 'unassigned' then ?
                    else split
                end,
                source_id = coalesce(nullif(source_id, ''), ? || ':' || clip_id),
                redistribution_allowed = coalesce(redistribution_allowed, 0)
            where {where}
            """,
            [split, source_prefix],
        )
        remaining = db.execute(
            """
            select count(*)
            from clips
            where source_type = 'synthetic'
              and transcript_type = 'synthetic'
              and notes like 'repair;%'
              and (split is null or split = '' or split = 'unassigned')
            """
        ).fetchone()[0]
    return {
        "split": split,
        "source_prefix": source_prefix,
        "matched": before["matched"] or 0,
        "assigned_split": before["split_missing"] or 0,
        "filled_source_id": before["source_missing"] or 0,
        "filled_redistribution_allowed": before["redistribution_missing"] or 0,
        "remaining_unassigned": remaining,
    }


def export_shard(
    path: str | Path,
    *,
    split: str | None = None,
    training_allowed: bool | None = None,
    eval_allowed: bool | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    clauses, values = [], []
    if split is not None:
        clauses.append("split = ?")
        values.append(split)
    if training_allowed is not None:
        clauses.append("coalesce(training_allowed, 0) = ?")
        values.append(int(training_allowed))
    if eval_allowed is not None:
        clauses.append("coalesce(eval_allowed, 0) = ?")
        values.append(int(eval_allowed))
    where = " where " + " and ".join(clauses) if clauses else ""
    sql = f"select * from clips{where} order by clip_id"
    if limit is not None:
        sql += " limit ?"
        values.append(limit)
    init_ledger(path)
    with closing(sqlite3.connect(path)) as db:
        db.row_factory = sqlite3.Row
        return [dict(row) for row in db.execute(sql, values).fetchall()]
