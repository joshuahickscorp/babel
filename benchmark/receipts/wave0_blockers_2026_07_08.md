# Wave 0 Blockers - 2026-07-08

Wave 0 closed the local proof-loop gates, but Babel has not earned the harsher
7.6/10 Studio score yet. The remaining blocker is model evidence, not harness
readiness.

## Verified Commands

```bash
.venv/bin/python -m unittest discover -s tests -q
.venv/bin/babel ledger-stats archive/ledger.sqlite
.venv/bin/babel audit archive/ledger.sqlite
.venv/bin/babel phase-status archive/ledger.sqlite
.venv/bin/babel repair-hygiene archive/ledger.sqlite
.venv/bin/babel eval-repair eval/repair_eval.jsonl
.venv/bin/babel run-cycle archive/ledger.sqlite eval/baseline/local_scout_cpu_5h.metrics.json \
  --experiment-id wave1_run_cycle_local_scout_cpu_5h_2026_07_08 \
  --previous-json eval/baseline/tiny_baseline.metrics.json \
  --heldout-jsonl eval/baseline/local_scout_cpu_5h.held_out.jsonl
.venv/bin/babel worst-cell-plan archive/ledger.sqlite eval/baseline/local_scout_cpu_5h.metrics.json \
  --target-hours 10 --target-eval-clips 10 --limit 10
.venv/bin/babel quality-cards eval/baseline/local_scout_cpu_5h.held_out.jsonl \
  --metrics-json eval/baseline/local_scout_cpu_5h.metrics.json \
  --manifest-csv benchmark/manifest.csv \
  --output-dir benchmark/QUALITY_CARDS \
  --model-name local_scout_cpu_5h \
  --release-decision 'failed release gate: worst_group_wer 8.5625 > tiny 0.9596; parity_gap 7.8276 > tiny 0.934' \
  --receipt-path benchmark/receipts/wave1_run_cycle_local_scout_cpu_5h_2026_07_08.experiment.json
.venv/bin/babel repair-quality-cards eval/repair_eval.jsonl \
  --output-dir benchmark/QUALITY_CARDS/stage_b_repair \
  --model-name stage_b_repair_seed \
  --release-decision 'not release eligible: synthetic seed only; clarify_recall 0.5; hallucination_rate 0.125' \
  --receipt-path benchmark/receipts/wave0_stage_b_repair_seed_2026_07_08.experiment.json \
  --output-receipt benchmark/receipts/wave1_stage_b_repair_quality_cards_2026_07_08.json
.venv/bin/babel eval-nbest eval/nbest_eval.jsonl
.venv/bin/babel run-cycle archive/ledger.sqlite \
  benchmark/receipts/wave1_nbest_contract_metrics_2026_07_08.json \
  --experiment-id wave1_nbest_contract_seed_2026_07_08 \
  --exact-command '.venv/bin/babel eval-nbest eval/nbest_eval.jsonl' \
  --component stage_a5_nbest_contract \
  --heldout-jsonl benchmark/receipts/wave1_nbest_contract_heldout_2026_07_08.jsonl \
  --output-receipt benchmark/receipts/wave1_nbest_contract_seed_2026_07_08.experiment.json \
  --decision record_as_contract_evidence
.venv/bin/babel eval-segmentation eval/segmentation_eval.jsonl
.venv/bin/babel experiment-record archive/ledger.sqlite \
  benchmark/receipts/wave1_segmentation_contract_seed_2026_07_08.experiment.json
.venv/bin/babel studio-distillation-plan archive/ledger.sqlite \
  --metrics-json eval/baseline/local_scout_cpu_5h.metrics.json \
  --previous-json eval/baseline/tiny_baseline.metrics.json \
  --preflight-receipt benchmark/receipts/wave1_compute_preflight_2026_07_08.json \
  --worst-cell-plan benchmark/receipts/wave1_worst_cell_plan_2026_07_08.json \
  --manifest-csv benchmark/manifest.csv \
  --host-profile pre_studio_m3_pro_18gb \
  --target-profile mac_studio_m1_ultra_128gb \
  --seeds 13,29,47 \
  --top-cells 4 \
  --epochs 3 \
  --batch-size 4 \
  --eval-limit 0 \
  --output-receipt benchmark/receipts/wave2_studio_distillation_plan_2026_07_08.json
.venv/bin/babel group-dro-schedule archive/ledger.sqlite \
  eval/baseline/local_scout_cpu_5h.metrics.json \
  --worst-cell-plan benchmark/receipts/wave1_worst_cell_plan_2026_07_08.json \
  --studio-plan benchmark/receipts/wave2_studio_distillation_plan_2026_07_08.json \
  --target-hours 10 \
  --target-eval-clips 10 \
  --max-weight 8 \
  --temperature 1 \
  --top-groups 12 \
  --output-receipt benchmark/receipts/wave3_group_dro_schedule_2026_07_08.json
.venv/bin/babel acquisition-plan archive/ledger.sqlite \
  --schedule-receipt benchmark/receipts/wave3_group_dro_schedule_2026_07_08.json \
  --manifest-csv benchmark/manifest.csv \
  --target-hours 10 \
  --limit 8 \
  --output-receipt benchmark/receipts/wave4_acquisition_plan_2026_07_08.json
.venv/bin/babel acquisition-intake \
  benchmark/receipts/wave5_acquisition_intake_fixture_2026_07_08.jsonl \
  --acquisition-plan benchmark/receipts/wave4_acquisition_plan_2026_07_08.json \
  --manifest-csv benchmark/manifest.csv \
  --output-receipt benchmark/receipts/wave5_acquisition_intake_gate_2026_07_08.json
.venv/bin/babel benchmark-freeze \
  --manifest-csv benchmark/manifest.csv \
  --scorer-py benchmark/score.py \
  --governance-md benchmark/GOVERNANCE.md \
  --losses-md benchmark/babel_loses_here.md \
  --low-n-threshold 5 \
  --output-receipt benchmark/receipts/wave6_benchmark_freeze_2026_07_08.json
.venv/bin/babel validate-receipts benchmark/receipts/*.experiment.json \
  --output-json benchmark/receipts/wave1_receipt_validation_2026_07_08.json
.venv/bin/babel compute-preflight archive/ledger.sqlite \
  --workspace /Users/scammermike/Downloads/babel \
  --component acoustic_distillation \
  --min-free-gb 60 \
  --require-experiments 8 \
  --require-receipt benchmark/receipts/wave1_run_cycle_local_scout_cpu_5h_2026_07_08.experiment.json \
  --require-receipt benchmark/receipts/wave1_worst_cell_plan_2026_07_08.json \
  --require-receipt benchmark/receipts/wave1_stage_b_repair_quality_cards_2026_07_08.json \
  --require-receipt benchmark/receipts/wave1_receipt_validation_2026_07_08.json \
  --require-receipt benchmark/receipts/wave1_nbest_contract_seed_2026_07_08.experiment.json \
  --require-receipt benchmark/receipts/wave1_segmentation_contract_seed_2026_07_08.experiment.json \
  --require-receipt benchmark/receipts/wave2_studio_distillation_plan_2026_07_08.json \
  --require-receipt benchmark/receipts/wave3_group_dro_schedule_2026_07_08.json \
  --require-receipt benchmark/receipts/wave4_acquisition_plan_2026_07_08.json \
  --require-receipt benchmark/receipts/wave5_acquisition_intake_gate_2026_07_08.json \
  --require-receipt benchmark/receipts/wave6_benchmark_freeze_2026_07_08.json \
  --require-receipt benchmark/QUALITY_CARDS/luganda/wave1_local_scout_cpu_5h.md \
  --require-receipt benchmark/QUALITY_CARDS/ekpeye/wave1_local_scout_cpu_5h.md \
  --require-receipt benchmark/QUALITY_CARDS/stage_b_repair/british_isles/wave1_repair_seed.md \
  --output-receipt benchmark/receipts/wave1_compute_preflight_2026_07_08.json
```

## Current Gate State

- Tests: 39 passed.
- Ledger stats: 1,146,353 clips; 1,786.91 training hours; 18,433 eval clips;
  195 coverage cells; coverage entropy 0.0602; 8 recorded experiments after the
  first `babel run-cycle` custom-build receipts.
- Built-in audit: passed; no license, defect, unassigned-eligible, or split-leak
  issues.
- Phase status: all checks true, including `phase_0_contract_loop`,
  `phase_1_repair_gate`, and `runpod_ready`.
- Disk gate: reclaimed from about 12 GiB free to above the 60 GB floor before
  compute preflight.

## Evidence That Blocks A Model Claim

- Current machine is a MacBook Pro M3 Pro with 18 GB memory, not the target Mac
  Studio M1 Ultra with 128 GB memory and 8 TB SSD. Full acoustic distillation was
  not launched locally.
- `local_scout_cpu_5h` is non-release: worst-group WER 8.5625, parity gap 7.8276,
  release gate failed against `openai/whisper-tiny`.
- `scout_smoke_check` is also non-release: worst-group WER 1.5556, parity gap
  1.2431, release gate failed against the tiny smoke baseline.
- Stage B repair seed scoring is only a synthetic/text gate receipt: clean WER
  0.225, worst repair group 0.875, clarify recall 0.5, hallucination rate 0.125.
- N-best contract scoring is not a model claim. First-best worst-group WER is
  0.5 on the text fixture, the min-max parity gap is 0.5, and oracle WER is 0.0;
  this records repair headroom only.
- Segmentation scoring is not ASR WER. Boundary F1 is 0.4286, worst-group
  boundary F1 is 0.0, and the parity gap is 1.0; this records contract-loop
  failure for punctuation/casing/boundary restoration.
- Benchmark audio is score-and-cite only: 353 AfriSpeech-200 rows,
  CC-BY-NC-SA-4.0, redistributable `no`.
- Coverage entropy remains 0.0602, so future data work must target worst cells
  rather than add bulk hours.
- The first worst-cell schedule ranks `luganda`, `igbo`, `igala`, and `ekpeye`
  highest. Each has nonzero eval evidence but 0.0 ledgered training hours under
  the current accent-family grouping, so the next data work is targeted licensed
  training acquisition/assignment for those cells.
- `babel quality-cards` generated 13 per-accent cards for `local_scout_cpu_5h`.
  The cards include clip IDs, references, candidate outputs, WER/CER,
  license/split/redistribution status, release-gate failure, and explicit
  `not recorded` slots for teacher/repair outputs where the source artifact does
  not yet carry them.
- `babel compute-preflight` now gates compute readiness before acoustic
  distillation or Stage B training. The Wave 1 preflight passed structurally
  with disk, audit, phase, experiment, and receipt gates green. This is only
  permission to run a Studio experiment; it is not a model-quality claim.
- `babel studio-distillation-plan` generated the Wave 2 Studio launch manifest.
  It refuses full acoustic launch on this M3 Pro verifier, provides exact
  train/eval/run-cycle/quality-card commands for Studio seeds 13, 29, and 47,
  and records the license summary before compute. It also sets the release
  expectation to non-release because the top four worst cells (`luganda`,
  `igbo`, `igala`, `ekpeye`) have 0.0 ledgered training hours.
- Group-DRO is explicitly blocked until Babel records sampler weights by
  accent family, per-group loss, collapse-guard readings, per-group WER, exact
  command, and a worst-group failure example.
- `babel group-dro-schedule` now records sampler weights by accent family. The
  Wave 3 schedule ranks `luganda` first with sampler weight 4.0 and distribution
  share 0.1158, followed by `igbo`, `igala`, and `ekpeye`. It is still blocked:
  selected groups have 0.0 ledgered training hours, the Studio plan refuses
  launch on this host, and no exact Group-DRO training command/loss receipt has
  been recorded.
- `babel acquisition-plan` converts the zero-hour blocker into provenance-first
  target work. Wave 4 targets 10 hours each for `luganda`, `igbo`, `igala`,
  `ekpeye`, `igbo and yoruba`, `swahili`, `yoruba`, and `ikwere`; permits only
  EdACC current deposits 10283/8983, SLR70, or speechocean762 after license
  review; and records 353 manifest hashes as do-not-train evidence.
- `babel acquisition-intake` now hard-gates candidate rows before ledger-upsert.
  The Wave 5 mixed fixture intentionally exits nonzero: 1 EdACC-current-style
  `luganda` row passes, and 1 AfriSpeech/eval-hash/NC-license row is rejected
  for blocked source, bad license, redistribution flag, and manifest-hash
  contamination. This is gate evidence only, not newly acquired training audio.
- `babel benchmark-freeze` now records the frozen benchmark state. Wave 6 freezes
  `benchmark/manifest.csv` at hash
  `3e634c9358db4ed1aa490663cab1a3829d2e2df57a314cf2d21fab7941c8c862`,
  records 353 do-not-train hashes, scorer version `0.2.0-model-backend`, scorer
  hash `a908905a03aae253a5ae0823e3d98ef59abe3d6063ea9a2353303e6fbbbe14d2`,
  low-n groups, label-review groups, and the implemented R3 model scoring path.
  The remaining blocker is evidence: no public scored model row exists until
  Studio records exact command, model hash/source, device, worst-group WER,
  per-group table, release-gate decision, and a failure example.
- `babel repair-quality-cards` generated Stage B faithfulness cards. The
  `british_isles` seed card surfaces the planted repair failure: answer instead
  of clarify plus unsupported claims `riverside` and `noon`.
- `babel validate-receipts` now enforces the evidence contract for experiment
  receipts. Wave 1 validation checked 8 receipts and found 0 failures: model
  evidence receipts carry exact command, commit, split, license summary,
  worst-group WER, parity gap, per-group table, release-gate decision, and at
  least one failure example. Contract-evidence receipts must name their metric
  family and must not be reported as ASR WER or model-quality gains.

## Receipts

- `benchmark/receipts/wave0_turbo_baseline_2026_07_08.experiment.json`
- `benchmark/receipts/wave0_tiny_baseline_2026_07_08.experiment.json`
- `benchmark/receipts/wave0_scout_smoke_check_2026_07_08.experiment.json`
- `benchmark/receipts/wave0_local_scout_cpu_5h_2026_07_08.experiment.json`
- `benchmark/receipts/wave0_stage_b_repair_seed_2026_07_08.experiment.json`
- `benchmark/receipts/wave1_run_cycle_local_scout_cpu_5h_2026_07_08.experiment.json`
- `benchmark/receipts/wave1_nbest_contract_seed_2026_07_08.experiment.json`
- `benchmark/receipts/wave1_segmentation_contract_seed_2026_07_08.experiment.json`
- `benchmark/receipts/wave1_worst_cell_plan_2026_07_08.json`
- `benchmark/receipts/wave1_compute_preflight_2026_07_08.json`
- `benchmark/receipts/wave1_stage_b_repair_quality_cards_2026_07_08.json`
- `benchmark/receipts/wave1_receipt_validation_2026_07_08.json`
- `benchmark/receipts/wave2_studio_distillation_plan_2026_07_08.json`
- `benchmark/receipts/wave3_group_dro_schedule_2026_07_08.json`
- `benchmark/receipts/wave4_acquisition_plan_2026_07_08.json`
- `benchmark/receipts/wave5_acquisition_intake_gate_2026_07_08.json`
- `benchmark/receipts/wave6_benchmark_freeze_2026_07_08.json`
- `benchmark/QUALITY_CARDS/*/wave1_local_scout_cpu_5h.md`
- `benchmark/QUALITY_CARDS/stage_b_repair/*/wave1_repair_seed.md`
- `benchmark/babel_loses_here.md`

## Next Allowed Move

On the target Studio only: run a tiny full acoustic train-to-score loop, record
the experiment row, generate per-accent quality cards, and gate it by
worst-group WER and parity gap before launching longer distillation or Group-DRO
seeds. No average-WER-only improvement claim is allowed.
