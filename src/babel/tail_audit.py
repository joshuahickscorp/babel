"""CPU-heavy, low-memory audit over local tail audio shards.

This intentionally does not import torch or load ASR models. It parallelizes
audio decode/stat collection across tar shards, touching one wav at a time per
worker, and writes data-cleaning artifacts for the next training run.
"""
from __future__ import annotations

import argparse
import io
import json
import math
import os
import tarfile
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[2]


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open() as f:
        return [json.loads(line) for line in f if line.strip()]


def load_maps(clips_path: Path, transcripts_path: Path) -> tuple[dict[str, dict], dict[str, str]]:
    meta = {r["clip_id"]: r for r in read_jsonl(clips_path)}
    refs: dict[str, str] = {}
    for row in read_jsonl(transcripts_path):
        refs.setdefault(row["clip_id"], row.get("text", ""))
    return meta, refs


def dbfs(value: float) -> float:
    if value <= 0 or not math.isfinite(value):
        return -120.0
    return 20.0 * math.log10(value)


def flags_for(row: dict) -> list[str]:
    flags = []
    if row.get("error"):
        flags.append("decode_error")
        return flags
    if not row.get("has_meta"):
        flags.append("missing_meta")
    if not row.get("has_transcript"):
        flags.append("missing_transcript")
    if row.get("sample_rate_hz") != 16000:
        flags.append("sample_rate_not_16k")
    if row.get("channels", 1) != 1:
        flags.append("not_mono")
    if row.get("duration_s", 0) < 0.5:
        flags.append("too_short")
    if row.get("duration_s", 0) > 30.0:
        flags.append("too_long")
    if abs(row.get("duration_delta_s", 0.0)) > 0.25:
        flags.append("duration_metadata_mismatch")
    if row.get("rms_dbfs", -120.0) < -45.0:
        flags.append("low_rms")
    if row.get("peak_dbfs", -120.0) < -35.0:
        flags.append("very_low_peak")
    if row.get("clipping_frac", 0.0) > 0.001:
        flags.append("clipping")
    words = row.get("text_words", 0)
    wpm = row.get("wpm", 0.0)
    if words >= 3 and wpm > 240.0:
        flags.append("speech_rate_too_fast")
    if words >= 3 and wpm < 40.0:
        flags.append("speech_rate_too_slow")
    return flags


def audit_member(tar: tarfile.TarFile, member: tarfile.TarInfo, shard: str, meta: dict, refs: dict) -> dict:
    clip_id = Path(member.name).stem
    row = {
        "clip_id": clip_id,
        "shard": shard,
        "tar_member": member.name,
        "tar_size": member.size,
    }
    m = meta.get(clip_id, {})
    text = refs.get(clip_id, "")
    row.update({
        "source_id": m.get("source_id", ""),
        "accent_family": m.get("accent_family", ""),
        "fluency_tier": m.get("fluency_tier", ""),
        "noise_tier": m.get("noise_tier", ""),
        "has_meta": bool(m),
        "has_transcript": bool(text),
        "text_chars": len(text),
        "text_words": len(text.split()),
    })
    try:
        extracted = tar.extractfile(member)
        if extracted is None:
            raise RuntimeError("extractfile returned None")
        data = extracted.read()
        info = sf.info(io.BytesIO(data))
        audio, sr = sf.read(io.BytesIO(data), dtype="float32", always_2d=False)
        arr = np.asarray(audio, dtype=np.float32)
        if arr.ndim == 2:
            mono = arr.mean(axis=1)
            channels = arr.shape[1]
        else:
            mono = arr
            channels = 1
        duration_s = float(len(mono) / sr) if sr else 0.0
        abs_mono = np.abs(mono)
        peak = float(abs_mono.max()) if mono.size else 0.0
        rms = float(np.sqrt(np.mean(np.square(mono)))) if mono.size else 0.0
        silence_frac = float(np.mean(abs_mono < 1e-4)) if mono.size else 1.0
        clipping_frac = float(np.mean(abs_mono >= 0.999)) if mono.size else 0.0
        meta_duration = float(m.get("duration_s") or 0.0)
        words = row["text_words"]
        row.update({
            "sample_rate_hz": int(sr),
            "channels": int(channels),
            "frames": int(info.frames),
            "subtype": info.subtype,
            "duration_s": round(duration_s, 4),
            "metadata_duration_s": round(meta_duration, 4),
            "duration_delta_s": round(duration_s - meta_duration, 4),
            "rms_dbfs": round(dbfs(rms), 2),
            "peak_dbfs": round(dbfs(peak), 2),
            "silence_frac": round(silence_frac, 6),
            "clipping_frac": round(clipping_frac, 6),
            "wpm": round((words / duration_s) * 60.0, 2) if duration_s > 0 else 0.0,
            "error": "",
        })
    except Exception as exc:
        row["error"] = f"{type(exc).__name__}: {str(exc)[:180]}"
    row["flags"] = flags_for(row)
    return row


def audit_shard(args: tuple[str, str, dict, dict, int]) -> dict:
    tar_path_s, out_dir_s, meta, refs, max_clips = args
    tar_path = Path(tar_path_s)
    out_dir = Path(out_dir_s)
    rows_path = out_dir / "parts" / f"{tar_path.stem}.audio_audit.jsonl"
    summary_path = out_dir / "parts" / f"{tar_path.stem}.summary.json"
    rows_path.parent.mkdir(parents=True, exist_ok=True)

    summary = {
        "shard": tar_path.name,
        "rows": 0,
        "errors": 0,
        "duration_s": 0.0,
        "flag_counts": Counter(),
        "source_counts": Counter(),
        "accent_counts": Counter(),
    }
    with tarfile.open(tar_path) as tar, rows_path.open("w") as out:
        members = [m for m in tar.getmembers() if m.isfile() and m.name.lower().endswith(".wav")]
        if max_clips:
            members = members[:max_clips]
        for member in members:
            row = audit_member(tar, member, tar_path.name, meta, refs)
            out.write(json.dumps(row, sort_keys=True) + "\n")
            summary["rows"] += 1
            summary["errors"] += 1 if row.get("error") else 0
            summary["duration_s"] += float(row.get("duration_s") or 0.0)
            summary["flag_counts"].update(row.get("flags", []))
            summary["source_counts"].update([row.get("source_id") or "unknown"])
            summary["accent_counts"].update([row.get("accent_family") or "unknown"])

    json_summary = {
        **summary,
        "duration_s": round(summary["duration_s"], 2),
        "flag_counts": dict(summary["flag_counts"]),
        "source_counts": dict(summary["source_counts"]),
        "accent_counts": dict(summary["accent_counts"]),
        "rows_path": str(rows_path),
    }
    summary_path.write_text(json.dumps(json_summary, indent=2, sort_keys=True))
    return json_summary


def combine(out_dir: Path, summaries: list[dict]) -> dict:
    combined = out_dir / "tail_audio_audit.jsonl"
    excludes = out_dir / "exclude_candidates.jsonl"
    flag_counts: Counter = Counter()
    source_counts: Counter = Counter()
    accent_counts: Counter = Counter()
    rows = errors = excluded = 0
    duration_s = 0.0

    with combined.open("w") as all_out, excludes.open("w") as excl_out:
        for summary in sorted(summaries, key=lambda s: s["shard"]):
            for line in Path(summary["rows_path"]).open():
                row = json.loads(line)
                all_out.write(json.dumps(row, sort_keys=True) + "\n")
                rows += 1
                errors += 1 if row.get("error") else 0
                duration_s += float(row.get("duration_s") or 0.0)
                flag_counts.update(row.get("flags", []))
                source_counts.update([row.get("source_id") or "unknown"])
                accent_counts.update([row.get("accent_family") or "unknown"])
                if row.get("flags"):
                    excluded += 1
                    excl_out.write(json.dumps(row, sort_keys=True) + "\n")

    report = {
        "rows": rows,
        "errors": errors,
        "flagged_rows": excluded,
        "duration_hours": round(duration_s / 3600.0, 3),
        "flag_counts": dict(flag_counts.most_common()),
        "source_counts": dict(source_counts.most_common()),
        "accent_counts": dict(accent_counts.most_common()),
        "audio_audit_jsonl": str(combined),
        "exclude_candidates_jsonl": str(excludes),
    }
    (out_dir / "tail_audio_audit_report.json").write_text(json.dumps(report, indent=2, sort_keys=True))

    md = [
        "# CPU-Safe Tail Audio Audit",
        "",
        f"- Rows: {rows}",
        f"- Decode errors: {errors}",
        f"- Flagged rows: {excluded}",
        f"- Duration hours: {report['duration_hours']}",
        "",
        "## Flag Counts",
        "",
    ]
    if flag_counts:
        md.extend(f"- `{k}`: {v}" for k, v in flag_counts.most_common())
    else:
        md.append("- none")
    md.extend(["", "## Outputs", "", f"- `{combined}`", f"- `{excludes}`"])
    (out_dir / "tail_audio_audit_report.md").write_text("\n".join(md) + "\n")
    return report


def run_tail_audit(
    *,
    shards: str | Path | None = None,
    clips: str | Path | None = None,
    transcripts: str | Path | None = None,
    out: str | Path | None = None,
    workers: int | None = None,
    limit_shards: int = 0,
    max_clips_per_shard: int = 0,
) -> dict:
    shard_dir = Path(shards) if shards else ROOT / "local_tail" / "stable_shards"
    clips_path = Path(clips) if clips else ROOT / "local_tail" / "out" / "clips.jsonl"
    transcripts_path = Path(transcripts) if transcripts else ROOT / "local_tail" / "out" / "transcripts.jsonl"
    out_dir = Path(out) if out else ROOT / "local_tail" / "audit"

    shard_paths = sorted(shard_dir.glob("*.tar"))
    if limit_shards:
        shard_paths = shard_paths[:limit_shards]
    if not shard_paths:
        raise FileNotFoundError(f"no tar shards found in {shard_dir}")

    out_dir.mkdir(parents=True, exist_ok=True)
    meta, refs = load_maps(clips_path, transcripts_path)
    worker_count = max(1, min(workers or os.cpu_count() or 1, len(shard_paths)))
    print(f"[audit] shards={len(shard_paths)} workers={worker_count} out={out_dir}", flush=True)
    print("[audit] CPU/data-only path: no torch, no Whisper, no model weights.", flush=True)

    t0 = time.time()
    summaries: list[dict] = []
    tasks = [(str(shard), str(out_dir), meta, refs, max_clips_per_shard) for shard in shard_paths]
    with ProcessPoolExecutor(max_workers=worker_count) as ex:
        futs = [ex.submit(audit_shard, task) for task in tasks]
        for fut in as_completed(futs):
            summary = fut.result()
            summaries.append(summary)
            print(
                f"[audit] {summary['shard']} rows={summary['rows']} "
                f"errors={summary['errors']} hours={summary['duration_s'] / 3600.0:.2f}",
                flush=True,
            )

    report = combine(out_dir, summaries)
    elapsed_s = round(time.time() - t0, 1)
    print(f"[audit] complete in {elapsed_s:.1f}s", flush=True)
    print(f"[audit] report={out_dir / 'tail_audio_audit_report.md'}", flush=True)
    return {
        **report,
        "elapsed_s": elapsed_s,
        "report_json": str(out_dir / "tail_audio_audit_report.json"),
        "report_md": str(out_dir / "tail_audio_audit_report.md"),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--shards", default=str(ROOT / "local_tail" / "stable_shards"))
    ap.add_argument("--clips", default=str(ROOT / "local_tail" / "out" / "clips.jsonl"))
    ap.add_argument("--transcripts", default=str(ROOT / "local_tail" / "out" / "transcripts.jsonl"))
    ap.add_argument("--out", default=str(ROOT / "local_tail" / "audit"))
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 1)
    ap.add_argument("--limit-shards", type=int, default=0)
    ap.add_argument("--max-clips-per-shard", type=int, default=0)
    args = ap.parse_args(argv)

    run_tail_audit(
        shards=args.shards,
        clips=args.clips,
        transcripts=args.transcripts,
        out=args.out,
        workers=args.workers,
        limit_shards=args.limit_shards,
        max_clips_per_shard=args.max_clips_per_shard,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
