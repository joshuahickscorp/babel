# Quality Card: zulu

- **model:** local_scout_cpu_5h
- **release_decision:** failed release gate: worst_group_wer 8.5625 > tiny 0.9596; parity_gap 7.8276 > tiny 0.934
- **receipt:** benchmark/receipts/wave1_run_cycle_local_scout_cpu_5h_2026_07_08.experiment.json
- **group_wer:** 1.1111
- **worst_group_wer:** 8.5625
- **parity_gap:** 7.8276

## Worst Examples

### 1. `afrispeech-200-eval_cdcbfc87d62db298`

- **source:** afrispeech-200
- **split:** eval
- **license:** CC-BY-NC-SA-4.0
- **redistributable:** no
- **WER:** 1.1111
- **CER:** 0.3818
- **reference transcript:** Aditya Seal and Harsh Beniwal play the supporting roles.
- **candidate output:** Adit a seal and has been not fully the support of those who
- **teacher output:** not recorded
- **student output:** Adit a seal and has been not fully the support of those who
- **repair output:** not recorded
- **release decision:** failed release gate: worst_group_wer 8.5625 > tiny 0.9596; parity_gap 7.8276 > tiny 0.934
