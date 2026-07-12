# Wave 7 Launch Readiness Scorecard - 2026-07-08

This receipt updates Babel toward Studio 10/10 without claiming model quality.
Local work remains launch prep only.

## Verdict

Babel is ready to hand a proof-complete launch path to the target Studio, but it
is not a release-candidate ASR model. The current scored Babel candidate
`local_scout_cpu_5h` still fails release gates: worst-group WER 8.5625, parity
gap 7.8276, and average WER 3.8376 versus the tiny baseline thresholds.

Current Studio-readiness score: 7.0/10 launch prep, 2.5/10 model quality,
6.7/10 density health. No 10/10 claim is allowed until worst-group WER and
min-max parity improve under the release gates with receipts.

## Verified Gates

- Unit tests: `.venv/bin/python -m unittest discover -s tests -q` -> 39 passed.
- Ledger stats: 1,146,353 clips; 1,786.91 train hours; 18,433 eval clips; 195
  coverage cells; coverage entropy 0.0602; 8 experiments.
- `babel audit archive/ledger.sqlite --metrics-json eval/metrics.baseline.json`
  passed with no license, defect, unassigned-eligible, or split-leak failures.
- `babel phase-status archive/ledger.sqlite --metrics-json eval/metrics.baseline.json`
  has all checks true and no `next_needed`.
- `babel validate-receipts benchmark/receipts/*.experiment.json` checked 8
  experiment receipts, 0 failures.
- `babel compute-preflight ... --min-free-gb 60` passed after cleanup with
  60.215 GiB free and all required receipts present.

## Launch Blockers

- Worst cells with 0.0 ledgered training hours: `luganda`, `igbo`, `igala`,
  `ekpeye`, `igbo and yoruba`, `swahili`, `yoruba`, `ikwere`, `fulani`,
  `kanuri`.
- The next data move is licensed acquisition/intake for those cells, not more
  average-WER training. The current allowed-source plan is
  `benchmark/receipts/wave4_acquisition_plan_2026_07_08.json`.
- The acquisition-intake gate intentionally rejected the blocked AfriSpeech/NC
  fixture and accepted only the EdACC-current-style fixture. No real new
  training audio was claimed.
- Acoustic distillation is Studio-only. The plan in
  `benchmark/receipts/wave2_studio_distillation_plan_2026_07_08.json` refuses
  full launch on this verifier host.
- Group-DRO remains blocked until selected groups have licensed training audio,
  exact commands, sampler/loss receipts, collapse-guard readings, per-group WER,
  and a worst-group failure example.
- Stage B repair remains synthetic contract evidence only: clarify recall 0.5,
  hallucination rate 0.125, not release eligible.

## Quality Cards

- Local scout quality cards exist under `benchmark/QUALITY_CARDS/*/wave1_local_scout_cpu_5h.md`.
- Stage B faithfulness cards exist under
  `benchmark/QUALITY_CARDS/stage_b_repair/*/wave1_repair_seed.md`.
- `benchmark/babel_loses_here.md` is populated and preserves failure rows so the
  project cannot hide behind averages.

## Density Receipt

Before density pass:

- Repo footprint: 9.0G.
- Artifact mass: `archive` 1.1G, `local_tail` 5.5G, `models` 872M.
- Largest source files: `src/babel/core.py` 2,719 LOC, `tests/test_core.py`
  1,049 LOC, `src/babel/cli.py` 636 LOC.

After density pass:

- Repo footprint: 7.8G.
- Artifact mass: `archive` 517M, `local_tail` 5.5G, `models` 224M.
- Largest source files: `src/babel/core.py` 2,430 LOC,
  `tests/test_core.py` 1,049 LOC, `src/babel/cli.py` 636 LOC,
  `src/babel/quality.py` 302 LOC.
- Source split: quality-card and Stage B repair-card rendering moved from
  `src/babel/core.py` to `src/babel/quality.py`. Public imports and CLI
  commands are preserved.
- Cleanup: removed generated, gitignored, non-receipt artifacts
  `archive/clips.jsonl`, `models/local_scout_cpu_5h/autosave_step.pth`, and
  `models/local_scout_tiny_turbo_kd/autosave_step.pth`.
- Kept: exported failing scout checkpoints, eval receipts, quality cards,
  `archive/ledger.sqlite`, `archive/held_out_clips.jsonl`, and hard-linked
  `local_tail` shards.

## Next Allowed Move

On the target M1 Ultra Studio only: run the tiny train-to-score seed path from
the Studio distillation plan, validate receipts, generate quality cards, and
compare against tiny and turbo on the same score set. Do not launch Group-DRO or
claim model quality until the selected worst cells have licensed training audio
and worst-group WER plus parity move under the release gates.
