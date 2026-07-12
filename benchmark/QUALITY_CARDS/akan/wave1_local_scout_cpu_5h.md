# Quality Card: akan

- **model:** local_scout_cpu_5h
- **release_decision:** failed release gate: worst_group_wer 8.5625 > tiny 0.9596; parity_gap 7.8276 > tiny 0.934
- **receipt:** benchmark/receipts/wave1_run_cycle_local_scout_cpu_5h_2026_07_08.experiment.json
- **group_wer:** 0.7349
- **worst_group_wer:** 8.5625
- **parity_gap:** 7.8276

## Worst Examples

### 1. `afrispeech-200-eval_7fba2f648f5a957c`

- **source:** afrispeech-200
- **split:** eval
- **license:** CC-BY-NC-SA-4.0
- **redistributable:** no
- **WER:** 1.5
- **CER:** 0.6049
- **reference transcript:** Ducey could announce his decision on reopening the states economy later Wednesday.
- **candidate output:** Do you say could that mouse is the decision not to be opening the states economy later when it is the the the the
- **teacher output:** not recorded
- **student output:** Do you say could that mouse is the decision not to be opening the states economy later when it is the the the the
- **repair output:** not recorded
- **release decision:** failed release gate: worst_group_wer 8.5625 > tiny 0.9596; parity_gap 7.8276 > tiny 0.934

### 2. `afrispeech-200-eval_f7a2e2425c7e25aa`

- **source:** afrispeech-200
- **split:** eval
- **license:** CC-BY-NC-SA-4.0
- **redistributable:** no
- **WER:** 0.9643
- **CER:** 0.9308
- **reference transcript:** Next line. Plan: next line. Tablets Coartem, 4 tabs twice daily for 3 days and paracetamol 1gm 3x daily for 3 days. Next line. Signed: Dr Ugochinyere Zikoranaudodimma
- **candidate output:** Next slide, FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF
- **teacher output:** not recorded
- **student output:** Next slide, FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF
- **repair output:** not recorded
- **release decision:** failed release gate: worst_group_wer 8.5625 > tiny 0.9596; parity_gap 7.8276 > tiny 0.934

### 3. `afrispeech-200-eval_f6b48a86a73cd670`

- **source:** afrispeech-200
- **split:** eval
- **license:** CC-BY-NC-SA-4.0
- **redistributable:** no
- **WER:** 0.9231
- **CER:** 0.9559
- **reference transcript:** The W.H. and its media boosters have been pummeling Romney ever since.
- **candidate output:** The...............................................................................................................................
- **teacher output:** not recorded
- **student output:** The...............................................................................................................................
- **repair output:** not recorded
- **release decision:** failed release gate: worst_group_wer 8.5625 > tiny 0.9596; parity_gap 7.8276 > tiny 0.934
