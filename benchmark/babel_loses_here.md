# Babel Loses Here

This is the public failure ledger for Babel's worst-group-WER doctrine. It is
not a marketing page, and it is deliberately non-empty.

Current scored Babel candidate: `local_scout_cpu_5h`, a non-converged local
scout checkpoint recorded in
`benchmark/receipts/wave0_local_scout_cpu_5h_2026_07_08.experiment.json`.
It is **not releaseable**: worst-group WER is 8.5625 and the min-max parity gap
is 7.8276 on its 120-row held-out scout eval. The release gate fails against
`openai/whisper-tiny`.

The benchmark manifest in this checkout has 353 AfriSpeech-200 eval rows,
all `CC-BY-NC-SA-4.0`, `redistributable=no`. Audio is score-and-cite only and
must not be redistributed.

## Current Babel Losses

These rows compare the current non-release Babel scout to the existing scored
reference baselines. They are receipts that the project is still a workbench,
not a model-quality leader.

| accent_family | model that beats Babel | their WER | Babel WER | quality_card | receipt | date |
|---|---|---:|---:|---|---|---|
| luganda | `openai/whisper-large-v3-turbo` | 0.1875 | 8.5625 | `benchmark/QUALITY_CARDS/luganda/wave1_local_scout_cpu_5h.md` | `benchmark/receipts/wave1_run_cycle_local_scout_cpu_5h_2026_07_08.experiment.json` | 2026-07-08 |
| igbo | `openai/whisper-large-v3-turbo` | 0.2392 | 7.0517 | `benchmark/QUALITY_CARDS/igbo/wave1_local_scout_cpu_5h.md` | `benchmark/receipts/wave1_run_cycle_local_scout_cpu_5h_2026_07_08.experiment.json` | 2026-07-08 |
| igala | `openai/whisper-large-v3-turbo` | 0.3517 | 6.8938 | `benchmark/QUALITY_CARDS/igala/wave1_local_scout_cpu_5h.md` | `benchmark/receipts/wave1_run_cycle_local_scout_cpu_5h_2026_07_08.experiment.json` | 2026-07-08 |
| ekpeye | `openai/whisper-large-v3-turbo` | 0.5102 | 5.8601 | `benchmark/QUALITY_CARDS/ekpeye/wave1_local_scout_cpu_5h.md` | `benchmark/receipts/wave1_run_cycle_local_scout_cpu_5h_2026_07_08.experiment.json` | 2026-07-08 |
| swahili | `openai/whisper-large-v3-turbo` | 0.2053 | 3.9048 | `benchmark/QUALITY_CARDS/swahili/wave1_local_scout_cpu_5h.md` | `benchmark/receipts/wave1_run_cycle_local_scout_cpu_5h_2026_07_08.experiment.json` | 2026-07-08 |
| yoruba | `openai/whisper-large-v3-turbo` | 0.3154 | 3.5133 | `benchmark/QUALITY_CARDS/yoruba/wave1_local_scout_cpu_5h.md` | `benchmark/receipts/wave1_run_cycle_local_scout_cpu_5h_2026_07_08.experiment.json` | 2026-07-08 |
| ikwere | `openai/whisper-large-v3-turbo` | 0.2384 | 2.9803 | `benchmark/QUALITY_CARDS/ikwere/wave1_local_scout_cpu_5h.md` | `benchmark/receipts/wave1_run_cycle_local_scout_cpu_5h_2026_07_08.experiment.json` | 2026-07-08 |

## Current Babel Failure Examples

Full hypotheses are preserved in the receipt JSON. The snippets below are kept
short so this page remains reviewable.

| clip_id | accent_family | WER | reference | Babel hypothesis snippet |
|---|---|---:|---|---|
| `afrispeech-200-eval_cd0624a1a6971590` | ekpeye | 31.5 | Stool OB+ golden liquid. | so, I'll cut blood blood blood... |
| `afrispeech-200-eval_aefec394d36e0c1f` | fulani | 18.2857 | The results were known late on Friday. | you will result we are more and more... |
| `afrispeech-200-eval_8e8e3ce038f47a16` | swahili | 17.4286 | Secure the container lid and label specimen. | Secure the container lid and level the space space... |

## Reference Baseline Failures

Even the teacher and tiny baseline lose badly in specific tail cells. These
failures stay on the page so a future Babel score cannot hide behind averages.

| model | clip_id | accent_family | WER | reference | hypothesis snippet |
|---|---|---|---:|---|---|
| `openai/whisper-large-v3-turbo` | `commonvoice-en-eval_eeb264770eb255c1` | mixed | 1.7143 | The participating schools came from around Singapore. | They're going to pick up a school, Kyl... |
| `openai/whisper-large-v3-turbo` | `afrispeech-200-eval_1aff19f5813b9f2b` | ekpeye | 1.5 | Echezonachukwu Kamsiyochukwu M.D. | Echezona Chuku Kamsi Yo Chuku MD. |
| `openai/whisper-tiny` | `afrispeech-200-eval_f60b9c38c2b7880c` | fulani | 2.0789 | These last few weeks have been difficult for anybody who was already living on the margins of society... | This last few weeks have been difficult... How is it? |
| `openai/whisper-tiny` | `afrispeech-200-eval_1aff19f5813b9f2b` | ekpeye | 2.0 | Echezonachukwu Kamsiyochukwu M.D. | and this is the Nachoku Kamsi Yocoku Mt. |

## Stage B Repair Failure

The Stage B repair seed is also non-release. It is text-only and synthetic, but
it proves the faithfulness gate catches unsupported repair behavior.

| accent_family | clean WER | quality_card | reference_clean | repair output | failure |
|---|---:|---|---|---|---|
| british_isles | 0.875 | `benchmark/QUALITY_CARDS/stage_b_repair/british_isles/wave1_repair_seed.md` | I think she said meet at the bank. | Meet at the riverside bank at noon. | Unsupported claims: `riverside`, `noon`; expected clarify, got answer. |

## Contract Failures

These are not model improvements. They are proof-loop fixtures that make future
Stage A.5 and segmentation claims harder to fake.

| contract | metric | worst group | parity gap | failure example | receipt |
|---|---:|---|---:|---|---|
| N-best first-best WER | 0.5 worst-group WER | east_asian | 0.5 | `she has three brothers` -> `she have three brother` | `benchmark/receipts/wave1_nbest_contract_seed_2026_07_08.experiment.json` |
| Segmentation boundary recovery | 0.0 worst-group boundary F1 | british_isles | 1.0 | `I went home. Are you OK?` -> `i went home are you ok` | `benchmark/receipts/wave1_segmentation_contract_seed_2026_07_08.experiment.json` |

## Update Rule

Every future Babel row added here must cite a receipt with:

- exact command;
- commit and dirty-worktree status;
- split and license summary;
- worst-group WER and min-max parity gap;
- per-group WER table;
- release-gate decision;
- at least one concrete failure example.

Use `babel run-cycle` to generate the receipt and record the experiment row
whenever possible.

Contract-evidence rows must name their metric family explicitly. Boundary F1,
punctuation, casing, and repair faithfulness are not ASR WER and must not be
reported as model-quality gains.

No average-WER-only claim belongs on this page.
