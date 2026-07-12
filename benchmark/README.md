# Babel Benchmark — the moat artifact

*Pre-Studio benchmark artifact (2026-06-27 scaffold, hardened 2026-07-08). Canonical spec:
`STUDIO_MAXIMIZATION_2026_06_27.md` §12 (Proof System) and §13 (Pre-Studio Scaffolding).*

A frozen, provenance-clean, speaker-disjoint, **real-audio-only**, accent-stratified ASR
eval, organized by **worst-group WER (never average)**. The benchmark's credibility — not
any checkpoint — is the deliverable (§9.Y K1, §12.12).

## Layout

| path | what |
|---|---|
| `manifest.csv` | The eval, 16-column §12.9 schema (`clip_id … clip_sha256`). 353 AfriSpeech-200 rows, all `redistributable: no`. `clip_sha256` doubles as the do-not-train-on-eval hash list. |
| `GOVERNANCE.md` | Metric definition, provenance rules, accent-label governance, R0–R5, freeze + "embarrass us" checklist. |
| `DATA_BLOCKLIST.md` | Non-redistributable / non-commercial sources. AfriSpeech-200 seeded as `eval-cite-only` / `commercial_train_ok: no`. |
| `BASELINES.md` | turbo (0.2211 avg / **0.8788** worst) + tiny (0.468 / **0.9596**), with the turbo per-cell card. |
| `score.py` | The scorer (worst-group WER + min-max gap). Metric + §12.9 I/O contract frozen; supports `--hyp <jsonl>` receipts and the lazy R3 `--model <path> --audio-root <dir>` Whisper scoring path. |
| `babel_loses_here.md` | The standing public "where Babel is not best" page, now populated with current failure evidence and launch blockers. |
| `QUALITY_CARDS/<cell>/` | Per named tail cell, clip-level diffed transcripts and Stage B faithfulness cards for current failing evidence rows. |
| `receipts/` | `receipts/<row_id>.json` scorer receipts (§12.9). |
| `scripts/build_manifest.py` | Hashes the 353 held-out wavs + fills provenance → `manifest.csv`. CPU-only. |

## The licensing constraint (read this — §10.4 P4)

> The current 353-clip eval is **AfriSpeech-200, CC BY-NC-SA 4.0 (non-commercial)**.
> It is **score-and-cite only**: every row is `redistributable: no`. We publish metrics +
> the hash list, never the audio, and never train a commercial model on it. Audio-shipping
> public rows must come from EdACC (10283/8983) / SLR70 / speechocean762 — see
> `DATA_BLOCKLIST.md`. **One improperly-redistributed clip is fatal.**

## Reproduce a Score

```bash
.venv/bin/python benchmark/score.py --manifest benchmark/manifest.csv \
    --hyp <hypotheses.jsonl> --model-name <name> --row-id <row> --write-receipt
```

`<hypotheses.jsonl>`: one `{"clip_id": ..., "hyp": ...}` per line. For R3 one-command
scoring on Studio, use the model path and explicit audio/device inputs:

```bash
.venv/bin/python benchmark/score.py --manifest benchmark/manifest.csv \
    --model <model-path-or-id> --audio-root archive/held_out --device mps \
    --model-name <name> --row-id <row> --write-receipt
```

Every claimed model row still needs the exact command, model hash/source, manifest hash,
license summary, worst-group WER, per-group table, release-gate decision, and a failure
example.

## Local Eval and Error Reports

```bash
.venv/bin/babel local-eval --model <model-path-or-id> --tag <tag> --device mps
.venv/bin/babel error-report
```

The old `scripts/local_eval.py` and `scripts/analyze_baseline_errors.py` paths remain as
compatibility shims for historical receipts.

## Local Tail Operations

```bash
.venv/bin/babel prepare-tail-shards
.venv/bin/babel tail-audit --workers 8
```

The old `scripts/prepare_stable_tail_shards.py` and `scripts/cpu_safe_tail_audit.py`
paths remain as compatibility shims for historical local-tail runs.

## Rebuild the manifest

```bash
.venv/bin/python benchmark/scripts/build_manifest.py
```
