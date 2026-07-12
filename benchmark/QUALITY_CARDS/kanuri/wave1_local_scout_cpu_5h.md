# Quality Card: kanuri

- **model:** local_scout_cpu_5h
- **release_decision:** failed release gate: worst_group_wer 8.5625 > tiny 0.9596; parity_gap 7.8276 > tiny 0.934
- **receipt:** benchmark/receipts/wave1_run_cycle_local_scout_cpu_5h_2026_07_08.experiment.json
- **group_wer:** 2.2846
- **worst_group_wer:** 8.5625
- **parity_gap:** 7.8276

## Worst Examples

### 1. `afrispeech-200-eval_10a9da57fcba7bb9`

- **source:** afrispeech-200
- **split:** eval
- **license:** CC-BY-NC-SA-4.0
- **redistributable:** no
- **WER:** 4.5385
- **CER:** 2.4432
- **reference transcript:** Wedge compression fracture of first thoracic vertebra, subsequent enco. TABLET, ORAL LORAZEPAM, LORAZEPAM, 0.5MG. Central cord syndrome at C5 level of cervical spinal cord, subsequent
- **candidate output:** Watch compression fracture of first to a thick photograph. Subsequent and cool. Tail plate, all are all all all all all all all all all all all all all all all all all all all all all all all all all all all all all all all all all all a...
- **teacher output:** not recorded
- **student output:** Watch compression fracture of first to a thick photograph. Subsequent and cool. Tail plate, all are all all all all all all all all all all all all all all all all all all all all all all all all all all all all all all all all all all a...
- **repair output:** not recorded
- **release decision:** failed release gate: worst_group_wer 8.5625 > tiny 0.9596; parity_gap 7.8276 > tiny 0.934

### 2. `afrispeech-200-eval_bace57c01ef284a5`

- **source:** afrispeech-200
- **split:** eval
- **license:** CC-BY-NC-SA-4.0
- **redistributable:** no
- **WER:** 2.6
- **CER:** 0.7123
- **reference transcript:** Spastic ectropion of left upper eyelid. INJECTABLE, INJECTION FAMOTIDINE, FAMOTIDINE, 10MG/ML. Intentional collision of motor vehicle with tree, sequela
- **candidate output:** Spastic Acropion of Left-Oper Eye Leade. Injectable, injection from Mootidine, from Mootidine, 10mg. Intentional collision of Motov vehicle with 3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-
- **teacher output:** not recorded
- **student output:** Spastic Acropion of Left-Oper Eye Leade. Injectable, injection from Mootidine, from Mootidine, 10mg. Intentional collision of Motov vehicle with 3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-
- **repair output:** not recorded
- **release decision:** failed release gate: worst_group_wer 8.5625 > tiny 0.9596; parity_gap 7.8276 > tiny 0.934

### 3. `afrispeech-200-eval_66d3eb658ef8ed41`

- **source:** afrispeech-200
- **split:** eval
- **license:** CC-BY-NC-SA-4.0
- **redistributable:** no
- **WER:** 1.0
- **CER:** 0.9346
- **reference transcript:** IMPRESSION: Mild left ventricular hypertrophy with preserved regional/global biventricular systolic function.
- **candidate output:** In Prashe,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,
- **teacher output:** not recorded
- **student output:** In Prashe,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,
- **repair output:** not recorded
- **release decision:** failed release gate: worst_group_wer 8.5625 > tiny 0.9596; parity_gap 7.8276 > tiny 0.934
