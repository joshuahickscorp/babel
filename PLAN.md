# Babel — local debugging plan (2026-06-18 → ~06-25)

Pod is **down**. All artifacts archived locally in `archive/`. This week is local-only ($0)
work to guarantee the next pod session trains instead of collapsing.

## Context: what happened
- Cycle4 distillation **collapsed** the flagship model — it emits a single repeated token
  (`!!!!` / `((((`), `worst_group_wer=1.0` across all 353 held-out clips.
- Confirmed real (not an eval artifact): base `large-v3-turbo` transcribes the same clip
  perfectly; the saved distilled checkpoint is degenerate.
- ~9 hrs of pod time was also lost earlier to a HALTED stall that wasn't caught promptly.

## What we have locally (archive/)
- `ledger.sqlite` — 1,146,353 labeled clips, all parity cells / splits / cycle1-3 consensus (integrity ok)
- `clips.jsonl` (563M) — ledger export (clip → cell metadata)
- `held_out/` — 353 eval clips WITH audio (86M) + `held_out_clips.jsonl`
- `labels/` — cycle1/2/3 outputs (pseudo_labels, synthetic_pairs, segmentation, traces.sft)
- `config/` — oracle_manifest.json, current_metrics, held_out eval transcripts + nbest
- Code: `~/Downloads/orchestrator/src/payload/babel_cloud/{distill,parity,evalpack,quantize}.py`

## Environment
- venv: `.venv` (python 3.12, matches pod's 3.12.3). torch (MPS), transformers, soundfile, librosa, jiwer.
- Whisper-tiny runs on MPS for cheap local collapse-repro.

## Phases
- [x] **0. Env** — venv + deps; verify whisper-tiny generate on one held-out clip via MPS.
- [ ] **1. Trustworthy eval + baseline** — fix evalpack (forced_decoder_ids conflict,
      attention_mask, pin language=en). Run base turbo + distil-large-v3.5 on 353 clips →
      real per-parity-cell WER → `baseline_metrics.json`. This is the bar distillation must beat.
      STATUS: local_eval.py written + bug-fixed. Waiting on model download (turbo ~1.5GB, in progress).
- [x] **2. Root-cause the collapse** ⭐ — CONFIRMED: fp16 training NaN.
      - fp16 → COLLAPSED at step 10 (loss=nan, uniq_ratio=0.016)
      - bf16 → healthy at step 40 (loss=1.977, uniq_ratio=1.0)
      - fp32 → also collapses (step 20, different mode: repetition, not NaN)
      → Fix: use bf16 for student training
- [x] **3. Fix + harden** — Applied to distill.py:
      1. `build_student(c).to(device).to(torch.bfloat16).train()` (student in bf16)
      2. feats cast to student dtype in _flush forward pass
      3. t_logits cast to student dtype before _kd_loss
      4. COLLAPSE_GUARD: unique_token_ratio check at step 50 and every 100 steps → raises
         RuntimeError("COLLAPSE_GUARD: ...") which _safe_flush re-raises (not swallowed)
- [x] **4. Ledger coverage** — pure-SQL analysis → `eval/ledger_coverage.json`.
      Key finding: 97.5% of train clips are accent_family='mixed' (CommonVoice, unannotated).
      Only 27,716 clips (~50h) are accent-specific. fluency_tier/noise_tier are NULL for all
      train clips — parity cells are accent_family only.
      Recommendation: --downsample-easy 0.076 for 3:1 ratio; runs.json already uses 0.4 (16:1).
- [x] **5. Cheap gated re-run** — "babel-cycle4-mini" stage added to runs.json:
      - Runs 5 shards, flagship tier only, 1 epoch
      - COLLAPSE_GUARD fires at step 50 if collapsed → non-zero exit blocks cycle4-distill
      - babel-cycle4-distill now depends_on babel-cycle4-mini
- [x] **6. Runbook** — collapse postmortem in RUNPOD.md (§8) + pod-back-up checklist written.
      Two root causes documented with bisection evidence. Stop-loss rules. cycle4-mini command.
      Full local dry-run: pending (Day 6).
- [x] **7. COLLAPSE_GUARD verified end-to-end** — `collapse_repro.py --student-dtype fp16 --steps 55`
      raises `RuntimeError: COLLAPSE_GUARD: flagship student degenerate at step 50`. Confirmed.
- [x] **8. grad_ckpt=False (new root cause)** — bf16 + gradient_checkpointing_enable() collapses
      via word repetition, loss *decreasing*, no nan. Gated behind `grad_ckpt: bool = False` in
      DistillConfig. H100 (80GB) needs no memory savings. Re-enable only after CUDA verification.
- [x] **9. Full bisection matrix** — bf16 healthy at lr ∈ {1e-4, 3e-5, 1e-5}; only grad_ckpt + use-gt paths collapse.
      Production path (bf16, no grad_ckpt, KD targets) is confirmed healthy across LR range.

## Pod-back-up gate (do NOT relaunch until ALL true)
1. [x] Local repro of collapse exists AND the fix makes it pass. ✅ DONE (bf16, no grad_ckpt)
2. [x] Collapse guard in distill.py aborts on degenerate output. ✅ DONE (verified fires step 50)
3. [x] cycle4-mini gate (few shards + eval) wired into the manifest. ✅ DONE
4. [x] Baseline WER per cell known. ✅ DONE (2026-06-18).
      turbo_baseline: avg_wer=0.2211, worst_group_wer=0.8788 ("english" accent family = 87.9%).
      parity_gap=0.8788. Results in eval/baseline/turbo_baseline.metrics.json.
      Note: "english" accent family in AfriSpeech is likely mislabeled Nigerian-accented English —
      this is the hardest target cell. Cycle 4 must beat this 87.9% worst-group WER.

**ALL 4 GATES MET. Pod can relaunch after relaunch pack (Day 7) is done.**

- [x] Local mini-cycle dry-run **PASSED** (2026-06-18): `[cycle4-mini] 5-shard pre-flight PASSED (no collapse detected)`
      5 WebDataset tar shards from held_out clips; DISTILL_DEVICE=mps; real distill.py code path; bf16, no grad_ckpt.
      Scripts: `scripts/make_local_shards.py` + DISTILL_DEVICE env var in distill.py.
- [x] Pod relaunch pack (Day 7): **COMPLETE** → `POD_RELAUNCH_PACK.md` (2026-06-18).
      Cost cap: $37 max (~13h at $2.69/hr H100). Wall-clock cap: 12h auto-stop.
      Exact commands for cycle4-mini (Step 3) and cycle4-distill (Step 4). Heartbeat, download, stop-loss.
      Remaining blockers: Cycle 2 corpus must be staged in R2; data staged on pod.

**ALL LOCAL GATES MET. Pod can relaunch when corpus shards are on pod and data is staged.**

## Extra local work (2026-06-18 session 4, per CLAUDE_LOCAL_WORK_QUEUE.md)

- [x] **Phase A: Tail acquisition COMPLETE** — 27716 clips, 50.4h, 5.8GB, 14 shards.
      Sources: SLR70 Nigerian (3359), Nigerian-accented-en (2721), EDACC (9288), EDACC-val (9848), SpeechOcean (2500).
      Files: `local_tail/out/clips.jsonl`, `local_tail/out/transcripts.jsonl`, `local_tail/stable_shards/` (14 shards).
- [x] **distill.py: dual-processor patch** — `student_processor_id` field allows cross-mel KD
      (turbo=128-mel teacher, tiny=80-mel student). Also patched `_kd_loss` to trim vocab mismatch (51866→51865).
- [ ] **Phase C scout distillation** (RUNNING) — turbo→tiny, 1 shard, lr=1e-5, CPU, PID 76871.
      Attempt 1 (lr=3e-5): COLLAPSED at step 100. Attempt 2 (lr=1e-5): passed steps 50/100/200 on MPS.
      Attempt 3 (lr=1e-5, CPU): running. Expected finish: ~4h from start.
- [ ] **Phase D: eval scout checkpoint** — after Phase C, run local_eval.py on scout checkpoint.
      Bar: beat tiny_smoketest avg_wer=0.5633 (20 clips). Target: directional improvement toward turbo's 0.2211.
- [ ] **Phase E: 3-shard longer scout** — after Phase D, run mini-shards=3, same lr.
- [ ] **Phase F: tail quality audit** — run turbo over all 14 stable shards, find bad transcripts.
