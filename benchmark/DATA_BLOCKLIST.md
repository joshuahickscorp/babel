# Data Blocklist — non-redistributable / non-commercial sources

*Seeded by the pre-Studio scaffolding (2026-06-27). Canonical: `STUDIO_MAXIMIZATION_2026_06_27.md` §10.6, §12.9, §13.0. **One improperly-redistributed clip is fatal (§10.4 P4).***

This file lists sources that are **score-and-cite only** and/or **non-commercial**, so they
must never (a) ship audio in the public/commercial benchmark, nor (b) be used to train any
commercial Babel model. Metrics, citations, and the do-not-train-on-eval hash list derived
from them are fine.

## Status legend

- `eval-cite-only` — may be scored on and cited; audio is **not** redistributed.
- `commercial_train_ok: no` — must **not** be in the training set of any commercial model.
- `redistributable: no` — audio bytes never shipped in the benchmark deposit.

## Entries

### AfriSpeech-200  (the current 353-clip held-out eval)

| field | value |
|---|---|
| source id | `intronhealth/afrispeech-200` (HF) |
| owner | Intron Health |
| license | **CC BY-NC-SA 4.0** (Attribution-NonCommercial-ShareAlike) |
| status | `eval-cite-only` |
| redistributable | **no** |
| commercial_train_ok | **no** |
| where it appears | ALL 353 rows of `manifest.csv` (`source=afrispeech-200`) |
| attribution string | `Intron Health -- AfriSpeech-200 (intronhealth/afrispeech-200), CC BY-NC-SA 4.0` |
| why blocked | Non-commercial license. We may publish worst-group metrics + the byte-hash list and cite the dataset, but we may **not** redistribute the audio in a commercial moat benchmark, and we may **not** train a commercial model on it. |
| related | AfriSpeech-Dialog (CC BY-NC-SA), AfriSpeech-MultiBench (CC BY-NC-SA, vendor-owned) — same constraint. |

> The whole current eval is AfriSpeech-200. That is why every `manifest.csv` row is
> `redistributable: no`. To ship a public benchmark with audio, backfill with the
> redistributable sources below — do not promote any AfriSpeech row to
> `redistributable: yes`.

## Allowed redistributable sources (for the audio-shipping public manifest — NOT yet added)

These are CC-BY / CC-BY-SA and may ship audio with attribution + a license-text diff:

| source | license | note |
|---|---|---|
| **EdACC — current DataShare deposit 10283/8983 (DOI 10.7488/ds/7914)** | CC-BY-SA 4.0 | **Cite 10283/8983; NEVER the withdrawn 10283/4836** (license-change supersession). |
| **OpenSLR SLR70** | CC-BY-SA 4.0 | Nigerian-English; matches the tail. |
| **speechocean762 (SLR101)** | CC-BY 4.0 | Pronunciation-scored read English. |

(Adding these is a Studio/extension task, not part of this scaffolding — see the Go-Prompt
in §13.C. The scaffolding only freezes the schema and the AfriSpeech metrics-only rows.)
