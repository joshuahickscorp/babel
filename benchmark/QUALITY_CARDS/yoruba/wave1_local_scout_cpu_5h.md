# Quality Card: yoruba

- **model:** local_scout_cpu_5h
- **release_decision:** failed release gate: worst_group_wer 8.5625 > tiny 0.9596; parity_gap 7.8276 > tiny 0.934
- **receipt:** benchmark/receipts/wave1_run_cycle_local_scout_cpu_5h_2026_07_08.experiment.json
- **group_wer:** 3.5133
- **worst_group_wer:** 8.5625
- **parity_gap:** 7.8276

## Worst Examples

### 1. `afrispeech-200-eval_63f850295b527ebb`

- **source:** afrispeech-200
- **split:** eval
- **license:** CC-BY-NC-SA-4.0
- **redistributable:** no
- **WER:** 10.8182
- **CER:** 6.963
- **reference transcript:** ENG is the gold standard for detecting unilateral peripheral vestibular disorders.
- **candidate output:** ENG is the good standard for detects and unilat there are very very very very very very very very very very very very very very very very very very very very very very very very very very very very very very very very very very very very...
- **teacher output:** not recorded
- **student output:** ENG is the good standard for detects and unilat there are very very very very very very very very very very very very very very very very very very very very very very very very very very very very very very very very very very very very...
- **repair output:** not recorded
- **release decision:** failed release gate: worst_group_wer 8.5625 > tiny 0.9596; parity_gap 7.8276 > tiny 0.934

### 2. `afrispeech-200-eval_8017c39af6ec1c24`

- **source:** afrispeech-200
- **split:** eval
- **license:** CC-BY-NC-SA-4.0
- **redistributable:** no
- **WER:** 7.1111
- **CER:** 6.8315
- **reference transcript:** Dr. Uloaku is w/ the Pt Onyinyechukwu at this time and has also spoken to Pt's neice Finidi
- **candidate output:** The arrow foot foot foot foot foot foot foot foot foot foot foot foot foot foot foot foot foot foot foot foot foot foot foot foot foot foot foot foot foot foot foot foot foot foot foot foot foot foot foot foot foot foot foot foot foot fo...
- **teacher output:** not recorded
- **student output:** The arrow foot foot foot foot foot foot foot foot foot foot foot foot foot foot foot foot foot foot foot foot foot foot foot foot foot foot foot foot foot foot foot foot foot foot foot foot foot foot foot foot foot foot foot foot foot fo...
- **repair output:** not recorded
- **release decision:** failed release gate: worst_group_wer 8.5625 > tiny 0.9596; parity_gap 7.8276 > tiny 0.934

### 3. `afrispeech-200-eval_1c7718998f8fbe89`

- **source:** afrispeech-200
- **split:** eval
- **license:** CC-BY-NC-SA-4.0
- **redistributable:** no
- **WER:** 7.0625
- **CER:** 3.0748
- **reference transcript:** Skull base foramen should be closely examined for enlargement that may be suggestive of perineural invasion.
- **candidate output:** The school base for a main should be closely examined for enlargements that may be suggestive of very nearer in in in in in in in in in in in in in in in in in in in in in in in in in in in in in in in in in in in in in in in in in in in...
- **teacher output:** not recorded
- **student output:** The school base for a main should be closely examined for enlargements that may be suggestive of very nearer in in in in in in in in in in in in in in in in in in in in in in in in in in in in in in in in in in in in in in in in in in in...
- **repair output:** not recorded
- **release decision:** failed release gate: worst_group_wer 8.5625 > tiny 0.9596; parity_gap 7.8276 > tiny 0.934
