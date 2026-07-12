# Quality Card: ikwere

- **model:** local_scout_cpu_5h
- **release_decision:** failed release gate: worst_group_wer 8.5625 > tiny 0.9596; parity_gap 7.8276 > tiny 0.934
- **receipt:** benchmark/receipts/wave1_run_cycle_local_scout_cpu_5h_2026_07_08.experiment.json
- **group_wer:** 2.9803
- **worst_group_wer:** 8.5625
- **parity_gap:** 7.8276

## Worst Examples

### 1. `afrispeech-200-eval_ceb8cd5dabef47a9`

- **source:** afrispeech-200
- **split:** eval
- **license:** CC-BY-NC-SA-4.0
- **redistributable:** no
- **WER:** 15.75
- **CER:** 9.0488
- **reference transcript:** It is northeast of Conway, the county seat.
- **candidate output:** which is not of of of of of of of of of of of of of of of of of of of of of of of of of of of of of of of of of of of of of of of of of of of of of of of of of of of of of of of of of of of of of of of of of of of of of of of of of of of...
- **teacher output:** not recorded
- **student output:** which is not of of of of of of of of of of of of of of of of of of of of of of of of of of of of of of of of of of of of of of of of of of of of of of of of of of of of of of of of of of of of of of of of of of of of of of of of of of of...
- **repair output:** not recorded
- **release decision:** failed release gate: worst_group_wer 8.5625 > tiny 0.9596; parity_gap 7.8276 > tiny 0.934

### 2. `afrispeech-200-eval_034aaa49f42cfb0d`

- **source:** afrispeech-200
- **split:** eval
- **license:** CC-BY-NC-SA-4.0
- **redistributable:** no
- **WER:** 12.1
- **CER:** 7.5556
- **reference transcript:** This is an entirely new model for fundraising, Brasher continued.
- **candidate output:** This is an entirely new model for for for for for for for for for for for for for for for for for for for for for for for for for for for for for for for for for for for for for for for for for for for for for for for for for for for for...
- **teacher output:** not recorded
- **student output:** This is an entirely new model for for for for for for for for for for for for for for for for for for for for for for for for for for for for for for for for for for for for for for for for for for for for for for for for for for for for...
- **repair output:** not recorded
- **release decision:** failed release gate: worst_group_wer 8.5625 > tiny 0.9596; parity_gap 7.8276 > tiny 0.934

### 3. `afrispeech-200-eval_2b0dac1e1a4d75db`

- **source:** afrispeech-200
- **split:** eval
- **license:** CC-BY-NC-SA-4.0
- **redistributable:** no
- **WER:** 9.3846
- **CER:** 9.6667
- **reference transcript:** In 1982, he was arrested and jailed by the communist regime until 1984.
- **candidate output:** In 19th century, it was arrested and was arrested and was arrested and was arrested and was arrested and was arrested and was arrested and was arrested and was arrested and was arrested and was arrested and was arrested and was arrested...
- **teacher output:** not recorded
- **student output:** In 19th century, it was arrested and was arrested and was arrested and was arrested and was arrested and was arrested and was arrested and was arrested and was arrested and was arrested and was arrested and was arrested and was arrested...
- **repair output:** not recorded
- **release decision:** failed release gate: worst_group_wer 8.5625 > tiny 0.9596; parity_gap 7.8276 > tiny 0.934
