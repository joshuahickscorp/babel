# Quality Card: ekpeye

- **model:** local_scout_cpu_5h
- **release_decision:** failed release gate: worst_group_wer 8.5625 > tiny 0.9596; parity_gap 7.8276 > tiny 0.934
- **receipt:** benchmark/receipts/wave1_run_cycle_local_scout_cpu_5h_2026_07_08.experiment.json
- **group_wer:** 5.8601
- **worst_group_wer:** 8.5625
- **parity_gap:** 7.8276

## Worst Examples

### 1. `afrispeech-200-eval_cd0624a1a6971590`

- **source:** afrispeech-200
- **split:** eval
- **license:** CC-BY-NC-SA-4.0
- **redistributable:** no
- **WER:** 31.5
- **CER:** 33.3636
- **reference transcript:** Stool OB+ golden liquid.
- **candidate output:** so, I'll cut blood blood blood blood blood blood blood blood blood blood blood blood blood blood blood blood blood blood blood blood blood blood blood blood blood blood blood blood blood blood blood blood blood blood blood blood blood bl...
- **teacher output:** not recorded
- **student output:** so, I'll cut blood blood blood blood blood blood blood blood blood blood blood blood blood blood blood blood blood blood blood blood blood blood blood blood blood blood blood blood blood blood blood blood blood blood blood blood blood bl...
- **repair output:** not recorded
- **release decision:** failed release gate: worst_group_wer 8.5625 > tiny 0.9596; parity_gap 7.8276 > tiny 0.934

### 2. `afrispeech-200-eval_1be811c6a6b5b059`

- **source:** afrispeech-200
- **split:** eval
- **license:** CC-BY-NC-SA-4.0
- **redistributable:** no
- **WER:** 14.0
- **CER:** 4.8627
- **reference transcript:** titrate pressors to maintain map >65 maintain cvp >10.
- **candidate output:** I treat the breast sauce to maintain a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a...
- **teacher output:** not recorded
- **student output:** I treat the breast sauce to maintain a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a...
- **repair output:** not recorded
- **release decision:** failed release gate: worst_group_wer 8.5625 > tiny 0.9596; parity_gap 7.8276 > tiny 0.934

### 3. `afrispeech-200-eval_beb5736d7750c2f4`

- **source:** afrispeech-200
- **split:** eval
- **license:** CC-BY-NC-SA-4.0
- **redistributable:** no
- **WER:** 11.9
- **CER:** 11.8305
- **reference transcript:** Card: general edema is decreasing but still 2+ in extremities.
- **candidate output:** The card, general edema is decreasing, is still still still still still still still still still still still still still still still still still still still still still still still still still still still still still still still still sti...
- **teacher output:** not recorded
- **student output:** The card, general edema is decreasing, is still still still still still still still still still still still still still still still still still still still still still still still still still still still still still still still still sti...
- **repair output:** not recorded
- **release decision:** failed release gate: worst_group_wer 8.5625 > tiny 0.9596; parity_gap 7.8276 > tiny 0.934
