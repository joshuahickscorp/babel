# Baselines

*Seeded by the pre-Studio scaffolding (2026-06-27) from the already-present eval artifacts
(`eval/baseline/turbo_baseline.metrics.json`, `tiny_baseline.metrics.json`). Scored on the
full **353-clip** AfriSpeech-200 held-out. Canonical: `STUDIO_MAXIMIZATION_2026_06_27.md`
§9.0, §12. **Headline metric = `worst_group_wer`, never average.***

## Reference rows (the numbers every Babel run must beat)

| model | tier | avg_wer | **worst_group_wer** | parity_gap | eval_utterances | repro_grade |
|---|---|---:|---:|---:|---:|:--:|
| `openai/whisper-large-v3-turbo` | teacher / external | 0.2211 | **0.8788** | 0.8788 | 353 | R2 |
| `openai/whisper-tiny` (un-KD) | student-floor / external | 0.4680 | **0.9596** | — | 353 | R2 |

- **Gate to pass (§9.0):** beat turbo's worst-group **0.8788** with `average_wer` not
  regressing past tiny's **0.4680**, and the COLLAPSE_GUARD never firing.
- 0.8788 average is the *stretch* on average; 0.8788 is the worst-group bar.

## Turbo per-cell card (the named tail, worst-first) — from `turbo_baseline.metrics.json`

| accent_family | turbo WER | role |
|---|---:|---|
| **english** (Nigerian) | **0.8788** | the mission cell; the worst-group number |
| zulu | 0.6667 | named tail (n=1 — CI caveat) |
| ekpeye | 0.5102 | named tail |
| igbo and yoruba | 0.4187 | composite Nigerian (label review) |
| fulani | 0.3547 | named tail |
| igala | 0.3517 | named tail |
| akan | 0.3476 | Ghanaian |
| yoruba | 0.3154 | Nigerian tail |
| ... | ... | (full card in the metrics json) |
| mixed | (easy majority) | 212/353 clips; never the cell a "win" improves |

> `kanuri` and `igbo` are also named/small tail cells; `igala`, `fulani`, `kanuri` are the
> other named cells from §9.0 alongside `english`/`zulu`/`ekpeye`.

## Refresh policy

- Every baseline refresh re-runs the scorer on the current frozen `manifest.csv` and updates
  these rows + the `babel_loses_here.md` page (§12.9 cadence).
- A pre-Studio "refresh" run (`turbo_refresh` / `tiny_refresh` tags via
  `scripts/local_eval.py`) may be recorded here once the teacher cache is complete; it must
  reproduce these numbers within bootstrap CI or the cold-restart stack changed something.
- The tiny no-collapse smoke run is a **recipe** check (does training+eval still run without
  collapse), **not** a baseline — its checkpoint is not a published row.
