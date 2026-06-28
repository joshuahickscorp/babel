# Babel Benchmark — the moat artifact

*Pre-Studio scaffolding skeleton (2026-06-27). Canonical spec:
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
| `score.py` | The scorer (worst-group WER + min-max gap). Metric + §12.9 I/O contract frozen; model-inference back-end is a clearly-marked stub. Today: `--hyp <jsonl>`. |
| `babel_loses_here.md` | The standing public "where Babel is not best" page (must be non-empty at launch). Stub. |
| `QUALITY_CARDS/<cell>/` | Per named tail cell, clip-level diffed transcripts (the visceral proof). Skeleton dirs. |
| `receipts/` | `receipts/<row_id>.json` scorer receipts (§12.9). |
| `scripts/build_manifest.py` | Hashes the 353 held-out wavs + fills provenance → `manifest.csv`. CPU-only. |

## The licensing constraint (read this — §10.4 P4)

> The current 353-clip eval is **AfriSpeech-200, CC BY-NC-SA 4.0 (non-commercial)**.
> It is **score-and-cite only**: every row is `redistributable: no`. We publish metrics +
> the hash list, never the audio, and never train a commercial model on it. Audio-shipping
> public rows must come from EdACC (10283/8983) / SLR70 / speechocean762 — see
> `DATA_BLOCKLIST.md`. **One improperly-redistributed clip is fatal.**

## Reproduce a score (today)

```bash
.venv/bin/python benchmark/score.py --manifest benchmark/manifest.csv \
    --hyp <hypotheses.jsonl> --model-name <name> --row-id <row> --write-receipt
```

`<hypotheses.jsonl>`: one `{"clip_id": ..., "hyp": ...}` per line. The R3 one-command
`--model <path>` path (load + transcribe on a stated device) is the Studio/extension fill-in.

## Rebuild the manifest

```bash
.venv/bin/python benchmark/scripts/build_manifest.py
```
