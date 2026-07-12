# Quality Card: english

- **model:** local_scout_cpu_5h
- **release_decision:** failed release gate: worst_group_wer 8.5625 > tiny 0.9596; parity_gap 7.8276 > tiny 0.934
- **receipt:** benchmark/receipts/wave1_run_cycle_local_scout_cpu_5h_2026_07_08.experiment.json
- **group_wer:** 0.9596
- **worst_group_wer:** 8.5625
- **parity_gap:** 7.8276

## Worst Examples

### 1. `afrispeech-200-eval_e827343b56482819`

- **source:** afrispeech-200
- **split:** eval
- **license:** CC-BY-NC-SA-4.0
- **redistributable:** no
- **WER:** 0.9596
- **CER:** 0.9005
- **reference transcript:** Aspirin 325 q.d. ; albuterol nebs 2.5 mg q. 4h ; Colace 100 mg b.i.d. ; heparin 5,000 units subcu b.i.d. ; Synthroid 200 mcg q.d. ; Ocean Spray 2 sprays q. i.d. ; simvastatin 10 mg q. h.s. ; Flovent 220 mcg 2 puffs b.i.d. ; Zantac 150 b....
- **candidate output:** As per in 325 QD, I would earn next to 0.5 MGQ for R..
- **teacher output:** not recorded
- **student output:** As per in 325 QD, I would earn next to 0.5 MGQ for R..
- **repair output:** not recorded
- **release decision:** failed release gate: worst_group_wer 8.5625 > tiny 0.9596; parity_gap 7.8276 > tiny 0.934
