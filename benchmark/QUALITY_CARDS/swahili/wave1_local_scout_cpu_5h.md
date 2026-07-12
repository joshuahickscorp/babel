# Quality Card: swahili

- **model:** local_scout_cpu_5h
- **release_decision:** failed release gate: worst_group_wer 8.5625 > tiny 0.9596; parity_gap 7.8276 > tiny 0.934
- **receipt:** benchmark/receipts/wave1_run_cycle_local_scout_cpu_5h_2026_07_08.experiment.json
- **group_wer:** 3.9048
- **worst_group_wer:** 8.5625
- **parity_gap:** 7.8276

## Worst Examples

### 1. `afrispeech-200-eval_8e8e3ce038f47a16`

- **source:** afrispeech-200
- **split:** eval
- **license:** CC-BY-NC-SA-4.0
- **redistributable:** no
- **WER:** 17.4286
- **CER:** 16.7442
- **reference transcript:** Secure the container lid and label specimen.
- **candidate output:** Secure the container lid and level the space space space space space space space space space space space space space space space space space space space space space space space space space space space space space space space space space...
- **teacher output:** not recorded
- **student output:** Secure the container lid and level the space space space space space space space space space space space space space space space space space space space space space space space space space space space space space space space space space...
- **repair output:** not recorded
- **release decision:** failed release gate: worst_group_wer 8.5625 > tiny 0.9596; parity_gap 7.8276 > tiny 0.934

### 2. `afrispeech-200-eval_1108d50988402600`

- **source:** afrispeech-200
- **split:** eval
- **license:** CC-BY-NC-SA-4.0
- **redistributable:** no
- **WER:** 7.2222
- **CER:** 1.8923
- **reference transcript:** Pituitary Adenomas Adenomas are the most common pituitary tumours.
- **candidate output:** The 3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3
- **teacher output:** not recorded
- **student output:** The 3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3-3
- **repair output:** not recorded
- **release decision:** failed release gate: worst_group_wer 8.5625 > tiny 0.9596; parity_gap 7.8276 > tiny 0.934

### 3. `afrispeech-200-eval_59ad4246dcb20e63`

- **source:** afrispeech-200
- **split:** eval
- **license:** CC-BY-NC-SA-4.0
- **redistributable:** no
- **WER:** 6.15
- **CER:** 2.8228
- **reference transcript:** When ligands stimulate cytokine receptors, the signal transducers and activators of transcription STAT proteins associate with the activated cytokine receptors.
- **candidate output:** When like and stimulated, you can receive the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the...
- **teacher output:** not recorded
- **student output:** When like and stimulated, you can receive the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the...
- **repair output:** not recorded
- **release decision:** failed release gate: worst_group_wer 8.5625 > tiny 0.9596; parity_gap 7.8276 > tiny 0.934
