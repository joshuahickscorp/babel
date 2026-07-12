# Stage B Repair Card: british_isles

- **model:** stage_b_repair_seed
- **release_decision:** not release eligible: synthetic seed only; clarify_recall 0.5; hallucination_rate 0.125
- **receipt:** benchmark/receipts/wave0_stage_b_repair_seed_2026_07_08.experiment.json
- **split:** synthetic repair seed; no held-out audio
- **license:** text-only synthetic/illustrative repair eval; no licensed audio
- **clean_wer:** 0.225
- **group_clean_wer:** 0.875
- **worst_group_wer:** 0.875
- **parity_gap:** 0.875
- **decision_accuracy:** 0.875
- **clarify_precision:** 1.0
- **clarify_recall:** 0.5
- **hallucination_rate:** 0.125

## Faithfulness Examples

### 1. `repair_0008`

- **faithfulness:** fail
- **decision:** answer
- **should_clarify:** True
- **unsupported_claims:** riverside, noon
- **clean WER:** 0.875
- **clean CER:** 0.7879
- **reference_clean:** I think she said meet at the bank.
- **repair output:** Meet at the riverside bank at noon.
- **release decision:** not release eligible: synthetic seed only; clarify_recall 0.5; hallucination_rate 0.125
