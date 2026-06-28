# Benchmark Governance

*Seeded by the pre-Studio scaffolding (2026-06-27). Canonical spec: `STUDIO_MAXIMIZATION_2026_06_27.md` §12 (the Proof System) and §13 (Pre-Studio Scaffolding). The through-line metric is **worst-group WER**, never average.*

## 0. Purpose

This benchmark is the moat artifact (§9.Y K1, §12.12): a frozen, provenance-clean,
speaker-disjoint, **real-audio-only** accent-stratified eval, organized by worst-group
WER. Its credibility — not any single checkpoint — is the deliverable. A benchmark Babel
always wins is self-dealing and worthless (§12.11); the `babel_loses_here.md` page must be
non-empty.

## 1. The metric (hard invariant)

- **Headline = `worst_group_wer`** (min-over-accent: the maximum WER across accent-family
  groups). Then `min_max_gap` (max_group_wer − min_group_wer), then `parity_gap`, then
  `average_wer` only as a no-regress guard.
- A change that lowers `average_wer` while raising any named tail cell
  (`english`/Nigerian, `zulu`, `ekpeye`, `igala`, `fulani`, `kanuri`) is a **bad change**
  and is rejected (§6.3). "Improving clean English and calling it accessibility" is a
  listed quality trap.
- The `mixed`/CommonVoice cell is the easy majority (212/353 eval clips) and must **never**
  be the thing a "win" improves.

## 2. Provenance manifest (`manifest.csv`, schema §12.9 — 16 columns)

`clip_id, source, source_clip_ref, license, redistributable, attribution, accent_family,
accent_label_raw, speaker_id, split, duration_s, reference_text, fluency_tier, noise_tier,
notes, clip_sha256`

- Every clip carries a `license`, a `redistributable` flag, an `attribution` string, and a
  `clip_sha256` of the audio bytes.
- **`clip_sha256` is also the do-not-train-on-eval hash list (§12.9).** Any model whose
  training data contains one of these byte hashes is contaminated; its leaderboard row is
  void and shown struck-through (§12.5).
- A scored row is invalid unless its `manifest_hash` matches the current frozen manifest
  (§12.9 invalid-row rules).

## 3. Licensing rule (the asset rests on this — §10.4 P4, §12.11)

> **One improperly-redistributed clip is fatal.**

- The current 353-clip eval audio is **AfriSpeech-200, CC BY-NC-SA 4.0 (non-commercial)**.
  It is **score-and-cite only**: every manifest row is `redistributable: no`,
  `commercial_train_ok: no`. We may publish the metrics and the hash list; we may **not**
  redistribute the audio in a commercial moat benchmark, and we may **not** train any
  commercial model on it. See `DATA_BLOCKLIST.md`.
- Public rows that **ship audio** (`redistributable: yes`) must come only from the
  CC-BY / CC-BY-SA sources the plan names: **EdACC current deposit 10283/8983 (never the
  withdrawn 4836)**, **SLR70**, **speechocean762**. Each ships with a recorded
  per-source attribution string and a license-text diff against the canonical license.

## 4. Accent labels are governed (§12.9 label review)

- Every `accent_family` value must have a justification here before any per-cell claim
  ships. Disputed or potentially-offensive labels are documented and flagged for a
  community reviewer before the claim repeats (a `label-dispute` event).
- `accent_label_raw` preserves the source's original label; `accent_family` is our grouping
  key for Group-DRO and per-cell scoring. Re-grouping requires community review.

### Current eval groups (353 clips, AfriSpeech-200)

| accent_family | n | notes |
|---|---:|---|
| mixed | 212 | easy majority (CommonVoice-style); never the cell a "win" improves |
| ikwere | 29 | Nigerian tail |
| ekpeye | 25 | named tail cell |
| yoruba | 18 | Nigerian tail |
| fulani | 12 | named tail cell |
| igbo and yoruba | 12 | composite Nigerian label — flagged for label review |
| swahili | 10 | East African |
| akan | 6 | Ghanaian |
| United States English | 5 | control |
| igbo | 4 | Nigerian tail |
| kanuri | 4 | named tail cell |
| igala | 4 | named tail cell |
| England English | 3 | control |
| India and South Asia (...) | 3 | composite label — flagged for label review |
| luganda | 2 | small cell — report with CI, flag low-n |
| United States English,England English | 2 | composite label — flagged for label review |
| zulu | 1 | named tail cell; **n=1, report with CI and a low-n caveat** |
| english | 1 | the mission cell (Nigerian-English); turbo 0.8788; **n=1 caveat** |

> Low-n cells (`zulu`, `english`, `luganda`) carry bootstrap CIs (§12.9) and an explicit
> small-sample caveat; they are mission-critical but statistically thin until the
> redistributable sources backfill them.

## 5. Reproducibility gradient (R0–R5, §12.6)

- No **public** number below **R2** (score artifact + manifest hash).
- Flagship rows target **R3**: one-command `score.py --model <m> --manifest manifest.csv`
  reproducible on the stated device class (Mac Studio M2 Max 96 GB).
- R5 (external adoption) is the moat.

## 6. Freeze discipline

Freeze the public `manifest.csv` (record its `manifest_hash`) and `score.py`
(`scorer_version`) **before** sprinting on models. With the benchmark frozen, every run
produces a public worst-group row; without it, every run produces a private number.

## 7. "Embarrass us before launch" checklist (§12.11, run before any public release)

- [ ] Every clip licensed; no `redistributable: yes` row sourced from AfriSpeech.
- [ ] Babel visibly loses somewhere (`babel_loses_here.md` non-empty).
- [ ] Accent labels defensible; composite labels reviewed.
- [ ] Repair-delta slice (over-correction rate) published for any repair row.
- [ ] Baselines current.
- [ ] Scorer outsider-runnable (one command).
- [ ] On-device numbers measured, not asserted.
- [ ] Every public number ≥ R2.
