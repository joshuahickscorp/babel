# Quality Card: luganda

- **model:** local_scout_cpu_5h
- **release_decision:** failed release gate: worst_group_wer 8.5625 > tiny 0.9596; parity_gap 7.8276 > tiny 0.934
- **receipt:** benchmark/receipts/wave1_run_cycle_local_scout_cpu_5h_2026_07_08.experiment.json
- **group_wer:** 8.5625
- **worst_group_wer:** 8.5625
- **parity_gap:** 7.8276

## Worst Examples

### 1. `afrispeech-200-eval_d2e72116c5c9108a`

- **source:** afrispeech-200
- **split:** eval
- **license:** CC-BY-NC-SA-4.0
- **redistributable:** no
- **WER:** 15.75
- **CER:** 8.92
- **reference transcript:** Have a second person immobilize the cervical spine.
- **candidate output:** F a second case and I will not be able to be able to be able to be able to be able to be able to be able to be able to be able to be able to be able to be able to be able to be able to be able to be able to be able to be able to be able...
- **teacher output:** not recorded
- **student output:** F a second case and I will not be able to be able to be able to be able to be able to be able to be able to be able to be able to be able to be able to be able to be able to be able to be able to be able to be able to be able to be able...
- **repair output:** not recorded
- **release decision:** failed release gate: worst_group_wer 8.5625 > tiny 0.9596; parity_gap 7.8276 > tiny 0.934

### 2. `afrispeech-200-eval_369b2a27520bb290`

- **source:** afrispeech-200
- **split:** eval
- **license:** CC-BY-NC-SA-4.0
- **redistributable:** no
- **WER:** 1.375
- **CER:** 0.9615
- **reference transcript:** Some studies suggest that single daily dosing may actually be less nephrotoxic than more frequent dosing.
- **candidate output:** Some studies suggest that single day video video video video video video video video video video video video video video video video video video video video video
- **teacher output:** not recorded
- **student output:** Some studies suggest that single day video video video video video video video video video video video video video video video video video video video video video
- **repair output:** not recorded
- **release decision:** failed release gate: worst_group_wer 8.5625 > tiny 0.9596; parity_gap 7.8276 > tiny 0.934
