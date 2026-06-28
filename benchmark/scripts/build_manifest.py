#!/usr/bin/env python3
"""
build_manifest.py  --  Populate benchmark/manifest.csv for the 353-clip held-out eval.

Joins archive/held_out_clips.jsonl (clip_id / reference / accent_family / tiers) with
the bytes of each archive/held_out/<clip_id>.wav, computing clip_sha256 and filling the
exact 16-column provenance schema from STUDIO_MAXIMIZATION_2026_06_27.md §12.9.

LICENSING LANDMINE (§13.0 / §10.6): the held-out audio is AfriSpeech-200, which is
CC BY-NC-SA 4.0 (NON-COMMERCIAL). Every row written here is therefore:
    license          = CC-BY-NC-SA-4.0
    redistributable  = no          (metrics-only; never ships audio in a commercial moat)
    notes            = metrics-only: non-commercial source (AfriSpeech-200)
This is fine to SCORE ON and CITE; it is NOT redistributable. Public manifest rows that
ship audio (redistributable: yes) must come from EdACC (10283/8983) / SLR70 /
speechocean762 -- NOT from this eval set. See benchmark/DATA_BLOCKLIST.md.

The clip_sha256 column doubles as the DO-NOT-TRAIN-ON-EVAL hash list (§12.9): any model
whose training data contains one of these byte hashes is contaminated and its row is void.

CPU-only, streamed hashing, trivial RAM. Run from the repo root:
    .venv/bin/python benchmark/scripts/build_manifest.py
"""
import csv
import hashlib
import json
import pathlib
import sys
import wave
import contextlib

REPO = pathlib.Path(__file__).resolve().parents[2]
HELD_OUT_DIR = REPO / "archive" / "held_out"
HELD_OUT_JSONL = REPO / "archive" / "held_out_clips.jsonl"
OUT_CSV = REPO / "benchmark" / "manifest.csv"

# Exact 16-column header, §12.9 (order is load-bearing).
HEADER = [
    "clip_id",
    "source",
    "source_clip_ref",
    "license",
    "redistributable",
    "attribution",
    "accent_family",
    "accent_label_raw",
    "speaker_id",
    "split",
    "duration_s",
    "reference_text",
    "fluency_tier",
    "noise_tier",
    "notes",
    "clip_sha256",
]

# AfriSpeech-200 provenance constants (the eval set is wholly from this source).
SOURCE = "afrispeech-200"
LICENSE = "CC-BY-NC-SA-4.0"
REDISTRIBUTABLE = "no"  # non-commercial; metrics-only
ATTRIBUTION = "Intron Health -- AfriSpeech-200 (intronhealth/afrispeech-200), CC BY-NC-SA 4.0"
NOTES = "metrics-only: non-commercial source (AfriSpeech-200); score-and-cite only, not redistributable"


def sha256_of(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def duration_of(path: pathlib.Path) -> str:
    """Best-effort WAV duration in seconds; blank if not a parseable PCM WAV."""
    try:
        with contextlib.closing(wave.open(str(path), "rb")) as w:
            frames = w.getnframes()
            rate = w.getframerate()
            if rate:
                return f"{frames / float(rate):.3f}"
    except Exception:
        pass
    return ""


def main() -> int:
    if not HELD_OUT_JSONL.exists():
        print(f"ERROR: missing {HELD_OUT_JSONL}", file=sys.stderr)
        return 1
    rows = [json.loads(line) for line in open(HELD_OUT_JSONL) if line.strip()]

    written = 0
    missing = 0
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_CSV, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(HEADER)
        for r in rows:
            clip_id = r["clip_id"]
            wav = HELD_OUT_DIR / f"{clip_id}.wav"
            if wav.exists():
                sha = sha256_of(wav)
                dur = duration_of(wav)
            else:
                sha = ""
                dur = ""
                missing += 1
            raw = r.get("accent_label_raw", r["accent_family"])
            w.writerow([
                clip_id,
                SOURCE,
                clip_id,  # source_clip_ref: AfriSpeech eval id is the natural ref
                LICENSE,
                REDISTRIBUTABLE,
                ATTRIBUTION,
                r["accent_family"],
                raw,
                r.get("speaker_id", ""),  # speaker-disjoint; raw set lacks per-clip speaker ids
                "eval",
                dur,
                r["reference"],
                r.get("fluency_tier", "unknown"),
                r.get("noise_tier", "unknown"),
                NOTES,
                sha,
            ])
            written += 1

    print(f"wrote {OUT_CSV} with {written} rows ({missing} missing-audio rows had blank sha256)")
    print("ALL rows: license=CC-BY-NC-SA-4.0, redistributable=no (AfriSpeech-200, non-commercial).")
    print("clip_sha256 column == do-not-train-on-eval hash list (§12.9).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
