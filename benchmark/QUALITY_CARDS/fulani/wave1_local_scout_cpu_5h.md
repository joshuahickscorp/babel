# Quality Card: fulani

- **model:** local_scout_cpu_5h
- **release_decision:** failed release gate: worst_group_wer 8.5625 > tiny 0.9596; parity_gap 7.8276 > tiny 0.934
- **receipt:** benchmark/receipts/wave1_run_cycle_local_scout_cpu_5h_2026_07_08.experiment.json
- **group_wer:** 2.7881
- **worst_group_wer:** 8.5625
- **parity_gap:** 7.8276

## Worst Examples

### 1. `afrispeech-200-eval_aefec394d36e0c1f`

- **source:** afrispeech-200
- **split:** eval
- **license:** CC-BY-NC-SA-4.0
- **redistributable:** no
- **WER:** 18.2857
- **CER:** 14.8919
- **reference transcript:** The results were known late on Friday.
- **candidate output:** you will result we are more and more and more and more and more and more and more and more and more and more and more and more and more and more and more and more and more and more and more and more and more and more and more and more an...
- **teacher output:** not recorded
- **student output:** you will result we are more and more and more and more and more and more and more and more and more and more and more and more and more and more and more and more and more and more and more and more and more and more and more and more an...
- **repair output:** not recorded
- **release decision:** failed release gate: worst_group_wer 8.5625 > tiny 0.9596; parity_gap 7.8276 > tiny 0.934

### 2. `afrispeech-200-eval_a5e087b253ee0ce9`

- **source:** afrispeech-200
- **split:** eval
- **license:** CC-BY-NC-SA-4.0
- **redistributable:** no
- **WER:** 6.3
- **CER:** 4.9375
- **reference transcript:** The businesss 50-day moving average price is 22.98 and its 200 day moving average price is 20.01.
- **candidate output:** the business 50 I have in the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the...
- **teacher output:** not recorded
- **student output:** the business 50 I have in the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the...
- **repair output:** not recorded
- **release decision:** failed release gate: worst_group_wer 8.5625 > tiny 0.9596; parity_gap 7.8276 > tiny 0.934

### 3. `afrispeech-200-eval_f60b9c38c2b7880c`

- **source:** afrispeech-200
- **split:** eval
- **license:** CC-BY-NC-SA-4.0
- **redistributable:** no
- **WER:** 2.1053
- **CER:** 0.9362
- **reference transcript:** These last few weeks have been difficult for anybody who was already living on the margins of society - isolated due to mental health issues, housing insecurity, or those experiencing homelessness, BACS CEO Jamie Almanza said in a statem...
- **candidate output:** This last few weeks have been difficult for anybody who was already living on the margins of society. Dash has so let that due to mental health issues. How is it? How is it? How is it? How is it? How is it? How is it? How is it? How is i...
- **teacher output:** not recorded
- **student output:** This last few weeks have been difficult for anybody who was already living on the margins of society. Dash has so let that due to mental health issues. How is it? How is it? How is it? How is it? How is it? How is it? How is it? How is i...
- **repair output:** not recorded
- **release decision:** failed release gate: worst_group_wer 8.5625 > tiny 0.9596; parity_gap 7.8276 > tiny 0.934
