#!/usr/bin/env python3
"""Prepare stable local-tail shards for training.

The tail acquisition job may be writing the newest tar. This script validates tar
files, hard-links completed shards into a separate directory, and by default skips
the newest shard when acquisition is still running.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "local_tail" / "data" / "shards"
DST = ROOT / "local_tail" / "stable_shards"
OUT = ROOT / "local_tail" / "stable_shards_manifest.json"


def is_readable_tar(path: Path) -> tuple[bool, int]:
    try:
        with tarfile.open(path) as tf:
            members = [m for m in tf.getmembers() if m.isfile()]
        return True, len(members)
    except Exception:
        return False, 0


def link_or_copy(src: Path, dst: Path) -> str:
    if dst.exists() and dst.stat().st_size == src.stat().st_size:
        return "exists"
    dst.unlink(missing_ok=True)
    try:
        os.link(src, dst)
        return "linked"
    except OSError:
        shutil.copy2(src, dst)
        return "copied"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(SRC))
    ap.add_argument("--dst", default=str(DST))
    ap.add_argument("--keep-newest", action="store_true", help="include newest shard too")
    args = ap.parse_args()

    src = Path(args.src)
    dst = Path(args.dst)
    dst.mkdir(parents=True, exist_ok=True)

    shards = sorted(src.glob("*.tar"))
    skipped_newest = None
    if shards and not args.keep_newest:
        skipped_newest = max(shards, key=lambda p: p.stat().st_mtime)
        shards = [p for p in shards if p != skipped_newest]

    manifest = {
        "source": str(src),
        "dest": str(dst),
        "skipped_newest": str(skipped_newest) if skipped_newest else None,
        "shards": [],
        "total_clips": 0,
    }
    for shard in shards:
        ok, n = is_readable_tar(shard)
        row = {
            "name": shard.name,
            "source_size": shard.stat().st_size,
            "readable": ok,
            "clips": n,
            "action": "skipped",
        }
        if ok and n:
            row["action"] = link_or_copy(shard, dst / shard.name)
            manifest["total_clips"] += n
        manifest["shards"].append(row)

    OUT.write_text(json.dumps(manifest, indent=2, sort_keys=True))
    print(f"stable shards: {len([s for s in manifest['shards'] if s['action'] != 'skipped'])}")
    print(f"clips: {manifest['total_clips']}")
    if skipped_newest:
        print(f"skipped newest/in-progress: {skipped_newest.name}")
    print(f"manifest: {OUT}")


if __name__ == "__main__":
    main()
