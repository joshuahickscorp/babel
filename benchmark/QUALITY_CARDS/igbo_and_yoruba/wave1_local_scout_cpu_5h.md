# Quality Card: igbo and yoruba

- **model:** local_scout_cpu_5h
- **release_decision:** failed release gate: worst_group_wer 8.5625 > tiny 0.9596; parity_gap 7.8276 > tiny 0.934
- **receipt:** benchmark/receipts/wave1_run_cycle_local_scout_cpu_5h_2026_07_08.experiment.json
- **group_wer:** 4.1827
- **worst_group_wer:** 8.5625
- **parity_gap:** 7.8276

## Worst Examples

### 1. `afrispeech-200-eval_646958229c5a987b`

- **source:** afrispeech-200
- **split:** eval
- **license:** CC-BY-NC-SA-4.0
- **redistributable:** no
- **WER:** 11.6364
- **CER:** 11.85
- **reference transcript:** Nwabuaku had a spell requiring bagging during their Abosimagha session yesterday.
- **candidate output:** I will work with this pair of wearing wearing wearing wearing wearing wearing wearing wearing wearing wearing wearing wearing wearing wearing wearing wearing wearing wearing wearing wearing wearing wearing wearing wearing wearing wearing...
- **teacher output:** not recorded
- **student output:** I will work with this pair of wearing wearing wearing wearing wearing wearing wearing wearing wearing wearing wearing wearing wearing wearing wearing wearing wearing wearing wearing wearing wearing wearing wearing wearing wearing wearing...
- **repair output:** not recorded
- **release decision:** failed release gate: worst_group_wer 8.5625 > tiny 0.9596; parity_gap 7.8276 > tiny 0.934

### 2. `afrispeech-200-eval_37ebcd0673c7a1b0`

- **source:** afrispeech-200
- **split:** eval
- **license:** CC-BY-NC-SA-4.0
- **redistributable:** no
- **WER:** 11.3636
- **CER:** 13.1692
- **reference transcript:** The elderly clergy man, Revd Akanu Ekeoma developed a heart attack
- **candidate output:** The elderly clergy clergy clergy clergy clergy clergy clergy clergy clergy clergy clergy clergy clergy clergy clergy clergy clergy clergy clergy clergy clergy clergy clergy clergy clergy clergy clergy clergy clergy clergy clergy clergy c...
- **teacher output:** not recorded
- **student output:** The elderly clergy clergy clergy clergy clergy clergy clergy clergy clergy clergy clergy clergy clergy clergy clergy clergy clergy clergy clergy clergy clergy clergy clergy clergy clergy clergy clergy clergy clergy clergy clergy clergy c...
- **repair output:** not recorded
- **release decision:** failed release gate: worst_group_wer 8.5625 > tiny 0.9596; parity_gap 7.8276 > tiny 0.934

### 3. `afrispeech-200-eval_361458591acdf793`

- **source:** afrispeech-200
- **split:** eval
- **license:** CC-BY-NC-SA-4.0
- **redistributable:** no
- **WER:** 6.8889
- **CER:** 2.0796
- **reference transcript:** Patient Zeribe presented on account of ammenorrhea of 4 months. Next line. Hot flushes associated with night sweats
- **candidate output:** is a series that is presented in a account of, I am an a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a...
- **teacher output:** not recorded
- **student output:** is a series that is presented in a account of, I am an a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a...
- **repair output:** not recorded
- **release decision:** failed release gate: worst_group_wer 8.5625 > tiny 0.9596; parity_gap 7.8276 > tiny 0.934
