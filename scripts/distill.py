"""Local standalone distillation engine — babel CPU scouts.

Self-contained fork of the original orchestrator babel_cloud distill.py, adapted
for local CPU runs without cloud dependencies.

Differences from cloud version:
- No R2 fetching: shards are local tar files, streamed in-process
- No _common / shards relative imports: all helpers inline
- CPU-safe dtypes: float32 for teacher, student, and features on CPU device
- max_seconds / max_steps: time- and step-bounded runs
- autosave_step.pth: model + optimizer state every save_every steps (resumable)
- progress.json: written at log_every intervals (monitored by runner/user)
- exclude_list: path to jsonl of clip_ids to skip before they enter training
- mel feature cache: optional disk cache of extracted mel spectrograms (skip re-FFT)
"""
from __future__ import annotations

import json
import os
import tarfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

@dataclass
class DistillConfig:
    tier: str                           # "flagship" | "min_size"
    teacher_id: str
    init_id: str
    r2_remote: str                      # local: path to shard directory
    shards_prefix: str                  # local: unused, kept for API compat
    ckpt_dir: str
    stage_local: str = "/tmp/babel_scout_stage"
    epochs: int = 2
    lr: float = 1e-4
    encoder_lr: float = 0.0             # 0 → same as lr
    batch_size: int = 2
    alpha_kl: float = 0.8
    beta_ce: float = 1.0
    temperature: float = 2.0
    decoder_layers: int = 0             # 0 → tier default
    encoder_keep: float = 1.0
    clips: str = ""
    transcripts: str = ""
    gpus: int = 0
    save_every: int = 25
    log_every: int = 5
    max_steps: int = 0                  # 0 → unlimited
    max_seconds: int = 0               # 0 → unlimited
    mini_shards: int = 0               # 0 → all shards
    grad_ckpt: bool = False
    student_processor_id: str = ""     # set to load student's own processor (different n_mels)
    exclude_list: str = ""             # path to jsonl with clip_ids to skip
    mel_cache_dir: str = ""            # path to cache extracted mel tensors (speeds up multi-epoch)


def _tier_defaults(cfg: DistillConfig) -> DistillConfig:
    if cfg.decoder_layers == 0:
        cfg.decoder_layers = 4 if cfg.tier == "flagship" else 2
    if cfg.tier == "min_size" and cfg.encoder_keep >= 1.0:
        cfg.encoder_keep = 0.66
    return cfg


# ---------------------------------------------------------------------------
# Inline helpers (replace _common / shards cloud modules)
# ---------------------------------------------------------------------------

def _read_jsonl(path: str) -> Iterator[dict]:
    p = Path(path)
    if not p.exists():
        return
    with p.open() as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def _list_shards(shard_dir: str) -> list[Path]:
    return sorted(Path(shard_dir).glob("*.tar"))


def _iter_clip_audio(tar_path: Path, stage_local: str) -> Iterator[tuple[str, Path]]:
    """Yield (clip_id, wav_path) from a tar shard.  Extracts on first access; reuses on subsequent."""
    shard_stage = Path(stage_local) / tar_path.stem
    shard_stage.mkdir(parents=True, exist_ok=True)
    with tarfile.open(tar_path) as tf:
        for member in tf.getmembers():
            if not member.name.endswith(".wav"):
                continue
            clip_id = Path(member.name).stem
            wav_path = shard_stage / Path(member.name).name
            if not wav_path.exists():
                try:
                    tf.extract(member, shard_stage, set_attrs=False)
                except TypeError:
                    tf.extract(member, shard_stage)
            yield clip_id, wav_path


def _load_exclude_set(path: str) -> set[str]:
    if not path:
        return set()
    return {r["clip_id"] for r in _read_jsonl(path) if "clip_id" in r}


def _write_progress(cfg: DistillConfig, step: int, elapsed: float,
                    stop_reason: str = "", extra: dict | None = None) -> None:
    p = Path(cfg.ckpt_dir)
    p.mkdir(parents=True, exist_ok=True)
    data: dict = {
        "step": step,
        "elapsed_seconds": round(elapsed, 1),
        "stop_reason": stop_reason,
        "device": os.environ.get("DISTILL_DEVICE", "cpu"),
        "tier": [cfg.tier],
        "teacher_id": cfg.teacher_id,
        "init_id": cfg.init_id,
        "student_processor_id": cfg.student_processor_id,
    }
    if extra:
        data.update(extra)
    (p / "progress.json").write_text(json.dumps(data, indent=2))


# ---------------------------------------------------------------------------
# Model helpers
# ---------------------------------------------------------------------------

def build_student(cfg: DistillConfig):
    import torch
    from transformers import WhisperForConditionalGeneration
    model = WhisperForConditionalGeneration.from_pretrained(cfg.init_id, torch_dtype=torch.float32)
    dec = model.model.decoder
    if len(dec.layers) > cfg.decoder_layers:
        keep = list(range(cfg.decoder_layers - 1)) + [len(dec.layers) - 1]
        dec.layers = torch.nn.ModuleList([dec.layers[i] for i in keep])
        model.config.decoder_layers = len(dec.layers)
    if cfg.tier == "min_size" and cfg.encoder_keep < 1.0:
        enc = model.model.encoder
        n = max(1, int(len(enc.layers) * cfg.encoder_keep))
        idx = (sorted(set(round(i * (len(enc.layers) - 1) / (n - 1)) for i in range(n)))
               if n > 1 else [0])
        enc.layers = torch.nn.ModuleList([enc.layers[i] for i in idx])
        model.config.encoder_layers = len(enc.layers)
    return model


def _optimizer(model, cfg: DistillConfig):
    import torch
    enc_lr = cfg.encoder_lr if cfg.encoder_lr > 0 else cfg.lr
    enc, other = [], []
    for name, p in model.named_parameters():
        (enc if ".encoder." in name else other).append(p)
    return torch.optim.AdamW([{"params": enc, "lr": enc_lr}, {"params": other, "lr": cfg.lr}])


def _kd_loss(student_logits, teacher_logits, labels, cfg: DistillConfig):
    import torch.nn.functional as F
    T = cfg.temperature
    V = student_logits.size(-1)
    mask = (labels != -100).reshape(-1)
    sl = student_logits.reshape(-1, V)[mask]
    # trim teacher to student vocab (turbo=51866 vs tiny=51865)
    tl = teacher_logits.reshape(-1, teacher_logits.size(-1))[:, :V][mask]
    kl = F.kl_div(F.log_softmax(sl / T, -1), F.softmax(tl / T, -1),
                  reduction="batchmean") * (T * T)
    ce = F.cross_entropy(student_logits.reshape(-1, V), labels.reshape(-1), ignore_index=-100)
    return cfg.alpha_kl * kl + cfg.beta_ce * ce


def _text_to_ids(proc, text: str, device: str):
    import torch
    pre = [t for _i, t in (proc.get_decoder_prompt_ids(language="en", task="transcribe") or [])]
    sot = proc.tokenizer.convert_tokens_to_ids("<|startoftranscript|>")
    body = proc.tokenizer(text, add_special_tokens=False).input_ids
    seq = [sot] + pre + body + [proc.tokenizer.eos_token_id]
    return torch.tensor([seq], device=device)


# ---------------------------------------------------------------------------
# Main training loop
# ---------------------------------------------------------------------------

def train_students(cfgs: list[DistillConfig]) -> list[str]:
    """Train one or more student tiers, sharing teacher and data stream.

    Returns list of checkpoint directories, one per cfg.
    """
    import torch
    from transformers import WhisperForConditionalGeneration, WhisperProcessor
    import soundfile as sf

    cfgs = [_tier_defaults(c) for c in cfgs]
    c0 = cfgs[0]

    device = os.environ.get("DISTILL_DEVICE", "cpu")
    start_time = time.time()

    # Dtype strategy: float32 on CPU (float16 emulated → slow + unstable),
    # float16/bfloat16 on MPS/CUDA.
    is_cpu = device == "cpu"
    teacher_dtype = torch.float32 if is_cpu else torch.float16
    student_dtype = torch.float32 if is_cpu else torch.bfloat16
    feature_dtype = torch.float32 if is_cpu else torch.float16

    print(f"[distill] device={device} teacher_dtype={teacher_dtype} student_dtype={student_dtype}",
          flush=True)

    # --- Load processors ---
    print(f"[distill] loading teacher processor: {c0.teacher_id}", flush=True)
    proc = WhisperProcessor.from_pretrained(c0.teacher_id)
    s_proc = (WhisperProcessor.from_pretrained(c0.student_processor_id)
              if c0.student_processor_id else None)

    # --- Load teacher ---
    print(f"[distill] loading teacher: {c0.teacher_id}", flush=True)
    teacher = (WhisperForConditionalGeneration
               .from_pretrained(c0.teacher_id, torch_dtype=teacher_dtype)
               .to(device).eval())

    # --- Load students ---
    ckpts = [Path(c.ckpt_dir) / f"stage_a_{c.tier}" for c in cfgs]
    students, opts = [], []
    for c in cfgs:
        print(f"[distill] loading student ({c.tier}): {c.init_id}", flush=True)
        s = build_student(c).to(device).to(student_dtype).train()
        if c.grad_ckpt:
            try:
                s.gradient_checkpointing_enable()
            except Exception:
                pass
        students.append(s)
        opts.append(_optimizer(s, c))

    # --- Resume from autosave if present ---
    _autosave = Path(c0.ckpt_dir) / "autosave_step.pth"
    step = 0
    if _autosave.exists():
        try:
            saved = torch.load(str(_autosave), map_location=device)
            for s, sd in zip(students, saved["models"]):
                s.load_state_dict(sd)
            for opt, osd in zip(opts, saved["optimizers"]):
                opt.load_state_dict(osd)
            step = saved.get("step", 0)
            print(f"[distill] resumed from autosave at step {step}", flush=True)
        except Exception as e:
            print(f"[distill] autosave load failed ({e}), starting fresh", flush=True)
            step = 0

    # --- Load metadata ---
    clip_meta: dict[str, dict] = {}
    if c0.clips:
        for r in _read_jsonl(c0.clips):
            clip_meta[r["clip_id"]] = r

    refs: dict[str, str] = {}
    if c0.transcripts:
        for r in _read_jsonl(c0.transcripts):
            refs.setdefault(r["clip_id"], r.get("text", ""))

    exclude_ids = _load_exclude_set(c0.exclude_list)
    if exclude_ids:
        print(f"[distill] exclude list: {len(exclude_ids)} clip_ids will be skipped", flush=True)

    # --- Shard list ---
    all_shards = _list_shards(c0.r2_remote)
    if not all_shards:
        raise RuntimeError(f"no .tar shards found in {c0.r2_remote}")
    if c0.mini_shards > 0:
        all_shards = all_shards[: c0.mini_shards]
    print(f"[distill] shards: {len(all_shards)}", flush=True)

    pad_id = proc.tokenizer.pad_token_id or proc.tokenizer.eos_token_id

    # --- Mel feature cache ---
    mel_cache: dict[str, object] = {}
    if c0.mel_cache_dir:
        Path(c0.mel_cache_dir).mkdir(parents=True, exist_ok=True)

    def _get_mel(clip_id: str, audio, sr: int):
        """Extract (t_feats, s_feats).  Uses disk cache when mel_cache_dir is set."""
        import torch as _t
        if c0.mel_cache_dir:
            cache_path = Path(c0.mel_cache_dir) / f"{clip_id}.pt"
            if cache_path.exists():
                cached = _t.load(str(cache_path), map_location="cpu")
                return (cached["t_feats"].to(device).to(feature_dtype),
                        cached["s_feats"].to(device).to(feature_dtype))
        tf = proc(audio, sampling_rate=sr, return_tensors="pt").input_features.to(device).to(feature_dtype)
        sf2 = (s_proc(audio, sampling_rate=sr, return_tensors="pt").input_features.to(device).to(feature_dtype)
               if s_proc else tf)
        if c0.mel_cache_dir:
            cache_path = Path(c0.mel_cache_dir) / f"{clip_id}.pt"
            _t.save({"t_feats": tf.cpu(), "s_feats": sf2.cpu()}, str(cache_path))
        return tf, sf2

    # --- Shared state ---
    buf: list[tuple] = []   # (t_feats, s_feats, tgt_or_None)
    _guard_probe: dict = {}
    stop_reason = ""

    # ---------------------------------------------------------------------------
    # Batch forward / backward
    # ---------------------------------------------------------------------------

    def _flush() -> None:
        if not buf:
            return
        t_feats_list = [f  for f, _sf, _t in buf]
        s_feats_list = [sf for _f, sf, _t in buf]
        tgts_list    = [t  for _f, _sf, t  in buf]

        t_feats = torch.cat(t_feats_list, 0)
        s_feats = torch.cat(s_feats_list, 0)

        # Collect guard probe (first clip seen)
        if "t_feats" not in _guard_probe:
            _guard_probe["t_feats"] = t_feats[:1].clone().detach()
            _guard_probe["s_feats"] = s_feats[:1].clone().detach()

        # Generate pseudo-labels for clips without GT text
        need_gen = [i for i, t in enumerate(tgts_list) if t is None]
        if need_gen:
            with torch.no_grad():
                gen_feats = torch.cat([t_feats[i:i+1] for i in need_gen], 0)
                gen_out = teacher.generate(gen_feats, max_new_tokens=128).split(1, 0)
            for idx, g in zip(need_gen, gen_out):
                tgts_list[idx] = g

        lmax = max(t.shape[1] for t in tgts_list)
        dec_in = torch.full((len(buf), lmax), pad_id, dtype=torch.long, device=device)
        labels  = torch.full((len(buf), lmax), -100,  dtype=torch.long, device=device)
        for i, t in enumerate(tgts_list):
            labels[i, :t.shape[1]] = dec_in[i, :t.shape[1]] = t[0]

        # Teacher forward (frozen) — shared across all students
        with torch.no_grad():
            t_logits = teacher(t_feats, decoder_input_ids=dec_in).logits

        for s, opt, c in zip(students, opts, cfgs):
            # student runs in student_dtype (bf16 on MPS); features are feature_dtype (fp16) for
            # the teacher, so cast to the student dtype here (matches the guard probe at generate).
            s_out = s(s_feats.to(student_dtype), decoder_input_ids=dec_in)
            loss = _kd_loss(s_out.logits, t_logits, labels, c)
            loss.backward()

        for opt in opts:
            opt.step()
            opt.zero_grad()

        buf.clear()

    def _safe_flush() -> None:
        try:
            _flush()
        except Exception as _e:
            if "COLLAPSE_GUARD" in str(_e):
                raise
            _estr = str(_e).lower()
            is_oom = "out of memory" in _estr or "device-side assert" in _estr
            print(f"[distill] {'OOM' if is_oom else 'ERR'} flush step={step}: "
                  f"{type(_e).__name__}: {str(_e)[:200]}", flush=True)
            buf.clear()
            for opt in opts:
                try:
                    opt.zero_grad(set_to_none=True)
                except Exception:
                    pass

    def _collapse_check(current_step: int) -> None:
        if current_step != 50 and current_step % 100 != 0:
            return
        for s, c in zip(students, cfgs):
            _pf = (_guard_probe.get("s_feats") if "s_feats" in _guard_probe
                   else _guard_probe.get("t_feats"))
            if _pf is None:
                return
            with torch.no_grad():
                _ids = s.generate(_pf.to(student_dtype), language="en",
                                   task="transcribe", max_new_tokens=64)
            _toks = _ids[0].tolist()
            _body = [t for t in _toks if t < proc.tokenizer.eos_token_id]
            _uniq = len(set(_body)) / max(1, len(_body))
            print(f"[distill] COLLAPSE_GUARD step={current_step} "
                  f"unique_token_ratio={_uniq:.3f} tier={c.tier}", flush=True)
            _write_progress(c0, current_step, time.time() - start_time,
                            extra={"collapse_guard_unique_token_ratio": _uniq})
            if _uniq < 0.2:
                raise RuntimeError(
                    f"COLLAPSE_GUARD: {c.tier} student degenerate at step {current_step} "
                    f"(unique_token_ratio={_uniq:.3f}, dtype={student_dtype}). "
                    "Training aborted — check student dtype and learning rate.")

    # ---------------------------------------------------------------------------
    # Training loop
    # ---------------------------------------------------------------------------

    def _autosave_now(current_step: int) -> None:
        Path(c0.ckpt_dir).mkdir(parents=True, exist_ok=True)
        torch.save({
            "step": current_step,
            "models": [s.state_dict() for s in students],
            "optimizers": [opt.state_dict() for opt in opts],
        }, str(_autosave))

    clips_seen = 0
    clips_skipped = 0

    try:
        for epoch in range(c0.epochs):
            for shard_path in all_shards:
                for clip_id, wav_path in _iter_clip_audio(shard_path, c0.stage_local):
                    # --- Stopping checks ---
                    elapsed = time.time() - start_time
                    if c0.max_seconds > 0 and elapsed >= c0.max_seconds:
                        stop_reason = f"max_seconds={c0.max_seconds}"
                        raise StopIteration
                    if c0.max_steps > 0 and step >= c0.max_steps:
                        stop_reason = f"max_steps={c0.max_steps}"
                        raise StopIteration

                    # --- Skip excluded clips ---
                    if clip_id in exclude_ids:
                        clips_skipped += 1
                        continue

                    # --- Load audio ---
                    try:
                        audio, sr = sf.read(str(wav_path))
                    except Exception as e:
                        print(f"[distill] skip {clip_id}: audio load error: {e}", flush=True)
                        continue

                    # --- Extract mel features ---
                    try:
                        t_feats, s_feats = _get_mel(clip_id, audio, sr)
                    except Exception as e:
                        print(f"[distill] skip {clip_id}: mel error: {e}", flush=True)
                        continue

                    # --- GT text → CE labels ---
                    ref = refs.get(clip_id)
                    tgt = _text_to_ids(proc, ref, device) if ref else None
                    buf.append((t_feats, s_feats, tgt))
                    clips_seen += 1

                    if len(buf) >= c0.batch_size:
                        try:
                            _safe_flush()
                        except RuntimeError as _e:
                            if "COLLAPSE_GUARD" in str(_e):
                                stop_reason = str(_e)
                                _write_progress(c0, step, time.time() - start_time,
                                                stop_reason=stop_reason)
                                raise StopIteration
                            raise
                        step += 1

                        _collapse_check(step)

                        # --- Logging ---
                        if step % c0.log_every == 0:
                            elapsed = time.time() - start_time
                            print(f"[distill] step={step} elapsed={elapsed:.0f}s "
                                  f"clips={clips_seen} skipped={clips_skipped}", flush=True)
                            _write_progress(c0, step, elapsed)

                        # --- Autosave ---
                        if step % c0.save_every == 0:
                            _autosave_now(step)
                            for s, ck in zip(students, ckpts):
                                ck.mkdir(parents=True, exist_ok=True)
                                s.save_pretrained(str(ck))
                            print(f"[distill] saved checkpoint at step {step}", flush=True)

    except StopIteration:
        pass

    # --- Final flush of partial batch ---
    if buf:
        try:
            _safe_flush()
            step += 1
        except RuntimeError as _e:
            if "COLLAPSE_GUARD" in str(_e):
                stop_reason = stop_reason or str(_e)
            else:
                raise

    # --- Final save ---
    elapsed = time.time() - start_time
    _write_progress(c0, step, elapsed, stop_reason=stop_reason)
    print(f"[distill] training done: step={step} elapsed={elapsed:.1f}s stop_reason={stop_reason!r}",
          flush=True)

    save_proc = s_proc or proc
    for s, ck, c in zip(students, ckpts, cfgs):
        ck.mkdir(parents=True, exist_ok=True)
        s.save_pretrained(str(ck))
        save_proc.save_pretrained(str(ck))
        print(f"[distill] checkpoint saved: {ck}", flush=True)

    return [str(ck) for ck in ckpts]
