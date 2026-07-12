# Quality Card: igbo

- **model:** local_scout_cpu_5h
- **release_decision:** failed release gate: worst_group_wer 8.5625 > tiny 0.9596; parity_gap 7.8276 > tiny 0.934
- **receipt:** benchmark/receipts/wave1_run_cycle_local_scout_cpu_5h_2026_07_08.experiment.json
- **group_wer:** 7.0517
- **worst_group_wer:** 8.5625
- **parity_gap:** 7.8276

## Worst Examples

### 1. `afrispeech-200-eval_0797d7be2b7dfdf8`

- **source:** afrispeech-200
- **split:** eval
- **license:** CC-BY-NC-SA-4.0
- **redistributable:** no
- **WER:** 15.875
- **CER:** 6.2
- **reference transcript:** Facial grimaces to turning and suctioning overbreathing vent.
- **candidate output:** special agreement is to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to...
- **teacher output:** not recorded
- **student output:** special agreement is to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to...
- **repair output:** not recorded
- **release decision:** failed release gate: worst_group_wer 8.5625 > tiny 0.9596; parity_gap 7.8276 > tiny 0.934

### 2. `afrispeech-200-eval_0edd44702840de34`

- **source:** afrispeech-200
- **split:** eval
- **license:** CC-BY-NC-SA-4.0
- **redistributable:** no
- **WER:** 6.2
- **CER:** 3.1261
- **reference transcript:** He was apparently well until 2 days ago when he developed high fever with associated chills and rigor. Next line.
- **candidate output:** He was apparently well on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on o...
- **teacher output:** not recorded
- **student output:** He was apparently well on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on o...
- **repair output:** not recorded
- **release decision:** failed release gate: worst_group_wer 8.5625 > tiny 0.9596; parity_gap 7.8276 > tiny 0.934

### 3. `afrispeech-200-eval_807cbb96509ee59a`

- **source:** afrispeech-200
- **split:** eval
- **license:** CC-BY-NC-SA-4.0
- **redistributable:** no
- **WER:** 5.95
- **CER:** 2.1589
- **reference transcript:** Kolade came down with Ebunilo disease, and was treated with Abimboye drug at Ede hospital on Sat 26 Dec, 1998
- **candidate output:** Polade came down with a vanilla disease comment and was treated with a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a...
- **teacher output:** not recorded
- **student output:** Polade came down with a vanilla disease comment and was treated with a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a a...
- **repair output:** not recorded
- **release decision:** failed release gate: worst_group_wer 8.5625 > tiny 0.9596; parity_gap 7.8276 > tiny 0.934
