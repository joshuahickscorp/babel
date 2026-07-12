# Quality Card: igala

- **model:** local_scout_cpu_5h
- **release_decision:** failed release gate: worst_group_wer 8.5625 > tiny 0.9596; parity_gap 7.8276 > tiny 0.934
- **receipt:** benchmark/receipts/wave1_run_cycle_local_scout_cpu_5h_2026_07_08.experiment.json
- **group_wer:** 6.8938
- **worst_group_wer:** 8.5625
- **parity_gap:** 7.8276

## Worst Examples

### 1. `afrispeech-200-eval_35793f8e299ea7de`

- **source:** afrispeech-200
- **split:** eval
- **license:** CC-BY-NC-SA-4.0
- **redistributable:** no
- **WER:** 12.4
- **CER:** 7.6458
- **reference transcript:** The terms for the male of a given animal species
- **candidate output:** It's time to the mail of the given on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on o...
- **teacher output:** not recorded
- **student output:** It's time to the mail of the given on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on on o...
- **repair output:** not recorded
- **release decision:** failed release gate: worst_group_wer 8.5625 > tiny 0.9596; parity_gap 7.8276 > tiny 0.934

### 2. `afrispeech-200-eval_d5fbea9d26a457c7`

- **source:** afrispeech-200
- **split:** eval
- **license:** CC-BY-NC-SA-4.0
- **redistributable:** no
- **WER:** 9.8462
- **CER:** 6.7416
- **reference transcript:** s SouthWest Service provides Monday-Saturday rail service at the Ashburn railroad station.
- **candidate output:** as south west south west west west west west west west west west west west west west west west west west west west west west west west west west west west west west west west west west west west west west west west west west west west we...
- **teacher output:** not recorded
- **student output:** as south west south west west west west west west west west west west west west west west west west west west west west west west west west west west west west west west west west west west west west west west west west west west west we...
- **repair output:** not recorded
- **release decision:** failed release gate: worst_group_wer 8.5625 > tiny 0.9596; parity_gap 7.8276 > tiny 0.934

### 3. `afrispeech-200-eval_87bc2f0b103682ce`

- **source:** afrispeech-200
- **split:** eval
- **license:** CC-BY-NC-SA-4.0
- **redistributable:** no
- **WER:** 4.8846
- **CER:** 2.2667
- **reference transcript:** The Womens WorldTour calendar is also scheduled to return with Strade Bianche on August 1, followed by the Vrgrda West Sweden time trial and road races.
- **candidate output:** you as for to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to t...
- **teacher output:** not recorded
- **student output:** you as for to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to t...
- **repair output:** not recorded
- **release decision:** failed release gate: worst_group_wer 8.5625 > tiny 0.9596; parity_gap 7.8276 > tiny 0.934
