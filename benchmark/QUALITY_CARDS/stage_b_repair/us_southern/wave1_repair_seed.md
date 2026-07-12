# Stage B Repair Card: us_southern

- **model:** stage_b_repair_seed
- **release_decision:** not release eligible: synthetic seed only; clarify_recall 0.5; hallucination_rate 0.125
- **receipt:** benchmark/receipts/wave0_stage_b_repair_seed_2026_07_08.experiment.json
- **split:** synthetic repair seed; no held-out audio
- **license:** text-only synthetic/illustrative repair eval; no licensed audio
- **clean_wer:** 0.225
- **group_clean_wer:** 0.0
- **worst_group_wer:** 0.875
- **parity_gap:** 0.875
- **decision_accuracy:** 0.875
- **clarify_precision:** 1.0
- **clarify_recall:** 0.5
- **hallucination_rate:** 0.125

## Faithfulness Examples

### 1. `repair_0006`

- **faithfulness:** pass
- **decision:** answer
- **should_clarify:** False
- **unsupported_claims:** none
- **clean WER:** 0.0
- **clean CER:** 0.0
- **reference_clean:** She was waiting outside.
- **repair output:** She was waiting outside.
- **release decision:** not release eligible: synthetic seed only; clarify_recall 0.5; hallucination_rate 0.125
