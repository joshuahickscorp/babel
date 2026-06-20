from __future__ import annotations

import json
import math
import hashlib
import re
import sqlite3
import unicodedata
import wave
from collections.abc import Mapping, Sequence
from contextlib import closing
from pathlib import Path
from typing import Any

TIERS = {"scout", "min_size", "flagship", "max_quality_local", "cloud_assurance"}
_CONF = {"type": "number", "min": 0.0, "max": 1.0}

# Declarative contract specs. A field spec carries: type ("number" | int | bool | str
# | dict | list), required, nullable, nonempty, enum, min/max (numbers), fields (dict),
# items (list element spec), len/min_len (lists). Cross-field invariants live in
# _stage_invariants so the engine itself stays generic.
STAGE_SPECS: dict[str, dict[str, Any]] = {
    "stage_a": {
        "type": dict,
        "fields": {
            "schema_version": {"type": str, "required": True, "nonempty": True},
            "audio": {
                "type": dict, "required": True,
                "fields": {
                    "source_id": {"type": str, "required": True, "nonempty": True},
                    "sample_rate_hz": {"type": int, "required": True, "min": 1},
                    "duration_s": {"type": "number", "required": True, "min": 0.0},
                    "channels": {"type": int, "min": 1},
                },
            },
            "decode": {
                "type": dict, "required": True,
                "fields": {
                    "model_id": {"type": str, "required": True, "nonempty": True},
                    "tier": {"type": str, "enum": TIERS},
                    "beam_size": {"type": int, "min": 1},
                    "temperature": {"type": "number", "min": 0.0},
                    "rtf": {"type": "number", "min": 0.0},
                },
            },
            "literal": {"type": str, "required": True},
            "nbest": {
                "type": list, "required": True, "min_len": 1,
                "items": {"type": dict, "fields": {
                    "rank": {"type": int, "required": True, "min": 1},
                    "text": {"type": str, "required": True},
                    "score": {"type": "number", "required": True},
                }},
            },
            "segments": {
                "type": list, "required": True, "min_len": 1,
                "items": {"type": dict, "fields": {
                    "start_s": {"type": "number", "required": True, "min": 0.0},
                    "end_s": {"type": "number", "required": True, "min": 0.0},
                    "text": {"type": str, "required": True},
                    "lang": {"type": str, "required": True},
                    "confidence": _CONF,
                }},
            },
            "signals": {
                "type": dict, "required": True,
                "fields": {
                    "asr_confidence": {**_CONF, "required": True},
                    "nbest_disagreement": _CONF,
                    "noise_tier": {"type": str},
                    "possible_code_switch": {"type": bool},
                    "accent_family_hint": {"type": str},
                    "needs_hard_path": {"type": bool},
                },
            },
        },
    },
    "stage_a5": {
        "type": dict,
        "fields": {
            "schema_version": {"type": str, "required": True, "nonempty": True},
            "source_id": {"type": str, "required": True, "nonempty": True},
            "punctuated": {"type": str, "required": True},
            "sentences": {
                "type": list, "required": True,
                "items": {"type": dict, "fields": {
                    "index": {"type": int, "required": True, "min": 0},
                    "text": {"type": str, "required": True},
                    "start_s": {"type": "number", "min": 0.0},
                    "end_s": {"type": "number", "min": 0.0},
                    "confidence": _CONF,
                }},
            },
            "tokens": {
                "type": list,
                "items": {"type": dict, "fields": {
                    "token": {"type": str, "required": True},
                    "source_token": {"type": str},
                    "punct_after": {"type": str},
                    "case": {"type": str, "enum": {"upper", "lower", "title", "mixed", "other"}},
                    "confidence": _CONF,
                }},
            },
            "signals": {
                "type": dict, "required": True,
                "fields": {
                    "boundary_confidence": _CONF,
                    "punctuation_confidence": _CONF,
                    "needs_repair": {"type": bool},
                },
            },
        },
    },
    "stage_b": {
        "type": dict,
        "fields": {
            "schema_version": {"type": str, "required": True, "nonempty": True},
            "source_id": {"type": str, "required": True, "nonempty": True},
            "cleaned": {"type": str, "nullable": True},
            "preserved_literal": {"type": str, "required": True},
            "intent": {
                "type": dict, "nullable": True,
                "fields": {
                    "type": {"type": str, "required": True},
                    "summary": {"type": str, "required": True},
                    "entities": {"type": list, "items": {"type": dict, "fields": {
                        "text": {"type": str, "required": True},
                        "type": {"type": str, "required": True},
                        "confidence": _CONF,
                    }}},
                },
            },
            "languages": {
                "type": list,
                "items": {"type": dict, "fields": {
                    "lang": {"type": str, "required": True},
                    "span": {"type": list, "len": 2, "items": {"type": int}},
                    "confidence": _CONF,
                }},
            },
            "faithfulness": {
                "type": dict, "required": True,
                "fields": {
                    "faithful": {"type": bool, "required": True},
                    "risk": {"type": str, "required": True},
                    "unsupported_claims": {"type": list, "required": True, "items": {"type": str}},
                },
            },
            "decision": {
                "type": dict, "required": True,
                "fields": {
                    "action": {"type": str, "required": True, "enum": {"answer", "clarify", "abstain"}},
                    "clarifying_question": {"type": str, "nullable": True},
                },
            },
            "confidence": {
                "type": dict, "required": True,
                "fields": {
                    "overall": {**_CONF, "required": True},
                    "intent": _CONF,
                    "entities": _CONF,
                },
            },
        },
    },
}

CLIP_COLUMNS = {
    "clip_id": "text primary key",
    "source_id": "text",
    "source_url": "text",
    "source_type": "text",
    "license_name": "text",
    "license_url": "text",
    "attribution": "text",
    "redistribution_allowed": "integer",
    "training_allowed": "integer",
    "eval_allowed": "integer",
    "duration_s": "real",
    "sample_rate_hz": "integer",
    "audio_hash": "text",
    "speaker_hash": "text",
    "split": "text",
    "transcript_type": "text",
    "transcript_confidence": "real",
    "teacher_agreement": "real",
    "accent_family": "text",
    "accent_confidence": "real",
    "l1_hint": "text",
    "fluency_tier": "text",
    "noise_tier": "text",
    "register": "text",
    "language_mix": "text",
    "cell_rarity": "real",
    "human_review_priority": "real",
    "pii_status": "text",
    "notes": "text",
}

EXPERIMENT_COLUMNS = {
    "experiment_id": "text primary key",
    "created_at": "text default current_timestamp",
    "hypothesis": "text",
    "component": "text",
    "data": "text",
    "metrics_json": "text",
    "decision": "text",
    "notes": "text",
}


def validate_stage(payload: Mapping[str, Any], stage: str) -> Mapping[str, Any]:
    if stage not in STAGE_SPECS:
        raise ValueError(f"unknown stage: {stage}")
    _validate(payload, STAGE_SPECS[stage], stage)
    version = str(payload["schema_version"])
    if not version.startswith(f"babel.{stage}."):
        raise ValueError(f"{stage} schema_version mismatch: {version}")
    _stage_invariants(payload, stage)
    return payload


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _validate(value: Any, spec: Mapping[str, Any], path: str) -> None:
    if value is None:
        if spec.get("nullable"):
            return
        raise ValueError(f"{path}: must not be null")
    expected = spec.get("type")
    if expected == "number":
        if not _is_number(value):
            raise ValueError(f"{path}: expected number")
    elif expected is bool:
        if not isinstance(value, bool):
            raise ValueError(f"{path}: expected bool")
    elif expected is int:
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError(f"{path}: expected int")
    elif expected is str:
        if not isinstance(value, str):
            raise ValueError(f"{path}: expected str")
        if spec.get("nonempty") and not value.strip():
            raise ValueError(f"{path}: must be non-empty")
    elif expected is dict:
        if not isinstance(value, Mapping):
            raise ValueError(f"{path}: expected object")
    elif expected is list:
        if not isinstance(value, list):
            raise ValueError(f"{path}: expected array")
    if "enum" in spec and value not in spec["enum"]:
        raise ValueError(f"{path}: {value!r} not one of {sorted(spec['enum'])}")
    if _is_number(value):
        if "min" in spec and value < spec["min"]:
            raise ValueError(f"{path}: {value} below minimum {spec['min']}")
        if "max" in spec and value > spec["max"]:
            raise ValueError(f"{path}: {value} above maximum {spec['max']}")
    if expected is dict:
        for name, field in spec.get("fields", {}).items():
            if name in value:
                _validate(value[name], field, f"{path}.{name}")
            elif field.get("required"):
                raise ValueError(f"{path}.{name}: required")
    if expected is list:
        if "len" in spec and len(value) != spec["len"]:
            raise ValueError(f"{path}: expected {spec['len']} item(s), got {len(value)}")
        if len(value) < spec.get("min_len", 0):
            raise ValueError(f"{path}: needs at least {spec['min_len']} item(s)")
        item = spec.get("items")
        if item is not None:
            for i, element in enumerate(value):
                _validate(element, item, f"{path}[{i}]")


def _stage_invariants(payload: Mapping[str, Any], stage: str) -> None:
    if stage == "stage_a":
        ranks = [item["rank"] for item in payload["nbest"]]
        if ranks != sorted(ranks) or len(set(ranks)) != len(ranks):
            raise ValueError("stage_a.nbest: ranks must be unique and ascending")
        for i, seg in enumerate(payload["segments"]):
            if seg["end_s"] < seg["start_s"]:
                raise ValueError(f"stage_a.segments[{i}]: end_s < start_s")
    elif stage == "stage_a5":
        for i, sent in enumerate(payload["sentences"]):
            start, end = sent.get("start_s"), sent.get("end_s")
            if start is not None and end is not None and end < start:
                raise ValueError(f"stage_a5.sentences[{i}]: end_s < start_s")
    elif stage == "stage_b":
        action = payload["decision"].get("action")
        if action == "clarify":
            question = payload["decision"].get("clarifying_question")
            if not (isinstance(question, str) and question.strip()):
                raise ValueError("stage_b.decision: clarify requires a clarifying_question")
        if action == "answer":
            if not (isinstance(payload.get("cleaned"), str) and payload["cleaned"].strip()):
                raise ValueError("stage_b: answer requires non-empty cleaned text")
            if not isinstance(payload.get("intent"), Mapping):
                raise ValueError("stage_b: answer requires an intent object")


def validate_dir(path: str | Path) -> dict[str, Any]:
    results = []
    for file in sorted(Path(path).glob("*.json")):
        payload = load_json(file)
        version = str(payload.get("schema_version", "")) if isinstance(payload, Mapping) else ""
        stage = next((s for s in STAGE_SPECS if version.startswith(f"babel.{s}.")), None)
        try:
            if stage is None:
                raise ValueError(f"unrecognized schema_version: {version!r}")
            validate_stage(payload, stage)
            results.append({"file": str(file), "stage": stage, "ok": True})
        except ValueError as exc:
            results.append({"file": str(file), "stage": stage, "ok": False, "error": str(exc)})
    return {"checked": len(results), "passed": sum(r["ok"] for r in results), "results": results}


def load_json(path: str | Path) -> Any:
    with Path(path).open() as file:
        return json.load(file)


def iter_jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows = []
    with Path(path).open() as file:
        for line_no, line in enumerate(file, 1):
            if line.strip():
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    raise ValueError(f"{path}:{line_no}: invalid JSONL") from exc
    return rows


def inspect_wav(path: str | Path, *, silence_floor: float = 0.01) -> dict[str, Any]:
    with wave.open(str(path), "rb") as wav:
        channels = wav.getnchannels()
        sample_rate = wav.getframerate()
        sample_width = wav.getsampwidth()
        frames = wav.getnframes()
        raw = wav.readframes(frames)
    samples = list(_pcm_values(raw, sample_width))
    if not samples:
        raise ValueError(f"{path}: no PCM samples")
    max_abs = float(1 << (sample_width * 8 - 1))
    normalized = [abs(sample) / max_abs for sample in samples]
    clipping_ratio = sum(value >= 0.999 for value in normalized) / len(normalized)
    silence_ratio = sum(value <= silence_floor for value in normalized) / len(normalized)
    rms = math.sqrt(sum(value * value for value in normalized) / len(normalized))
    flags = []
    if sample_rate < 16000:
        flags.append("low_sample_rate")
    if clipping_ratio > 0.01:
        flags.append("clipping")
    if rms < 0.005:
        flags.append("near_silent")
    return {
        "path": str(path),
        "channels": channels,
        "sample_rate_hz": sample_rate,
        "sample_width_bytes": sample_width,
        "frames": frames,
        "duration_s": frames / sample_rate if sample_rate else 0,
        "rms": rms,
        "peak": max(normalized),
        "clipping_ratio": clipping_ratio,
        "silence_ratio": silence_ratio,
        "flags": flags,
    }


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def manifest_wavs(
    root: str | Path,
    *,
    source_type: str = "local",
    license_name: str | None = None,
    license_url: str | None = None,
    training_allowed: bool = False,
    eval_allowed: bool = False,
) -> list[dict[str, Any]]:
    rows = []
    for path in sorted(Path(root).rglob("*.wav")):
        info = inspect_wav(path)
        audio_hash = file_sha256(path)
        flags = [*info["flags"]]
        if not license_name:
            flags.append("license_missing")
        rows.append(
            {
                "clip_id": audio_hash[:16],
                "source_id": str(path),
                "source_url": str(path),
                "source_type": source_type,
                "license_name": license_name,
                "license_url": license_url,
                "training_allowed": int(training_allowed and not flags),
                "eval_allowed": int(eval_allowed and not flags),
                "duration_s": info["duration_s"],
                "sample_rate_hz": info["sample_rate_hz"],
                "audio_hash": audio_hash,
                "split": "quarantine" if flags else "unassigned",
                "transcript_type": "unknown",
                "noise_tier": "defective" if info["flags"] else "unknown",
                "notes": ",".join(flags),
            }
        )
    return rows


def _pcm_values(raw: bytes, sample_width: int) -> list[int]:
    if sample_width not in (1, 2, 3, 4):
        raise ValueError(f"unsupported PCM sample width: {sample_width}")
    values = []
    for i in range(0, len(raw), sample_width):
        chunk = raw[i : i + sample_width]
        if len(chunk) != sample_width:
            break
        if sample_width == 1:
            values.append(chunk[0] - 128)
        else:
            value = int.from_bytes(chunk, "little", signed=False)
            sign_bit = 1 << (sample_width * 8 - 1)
            if value & sign_bit:
                value -= 1 << (sample_width * 8)
            values.append(value)
    return values


def normalize_words(text: str) -> list[str]:
    text = unicodedata.normalize("NFKC", text).casefold()
    text = re.sub(r"[^\w\s']", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text.split()


def edit_distance(reference: Sequence[Any], hypothesis: Sequence[Any]) -> int:
    row = list(range(len(hypothesis) + 1))
    for i, r in enumerate(reference, 1):
        prev, row[0] = row[0], i
        for j, h in enumerate(hypothesis, 1):
            old = row[j]
            row[j] = min(row[j] + 1, row[j - 1] + 1, prev + (r != h))
            prev = old
    return row[-1]


def wer(reference: str, hypothesis: str, *, normalize: bool = True) -> float:
    ref = normalize_words(reference) if normalize else reference.split()
    hyp = normalize_words(hypothesis) if normalize else hypothesis.split()
    if not ref:
        return 0.0 if not hyp else 1.0
    return edit_distance(ref, hyp) / len(ref)


def cer(reference: str, hypothesis: str, *, normalize: bool = True) -> float:
    ref_text = " ".join(normalize_words(reference)) if normalize else reference
    hyp_text = " ".join(normalize_words(hypothesis)) if normalize else hypothesis
    if not ref_text:
        return 0.0 if not hyp_text else 1.0
    return edit_distance(list(ref_text), list(hyp_text)) / len(ref_text)


def parity_gap(scores: Mapping[str, float], *, higher_is_better: bool = True) -> dict[str, Any]:
    if not scores:
        raise ValueError("scores cannot be empty")
    best = max(scores, key=scores.get) if higher_is_better else min(scores, key=scores.get)
    worst = min(scores, key=scores.get) if higher_is_better else max(scores, key=scores.get)
    return {"best": best, "worst": worst, "gap": abs(scores[best] - scores[worst])}


def eval_asr(
    rows: Sequence[Mapping[str, Any]],
    *,
    reference_key: str = "reference",
    hypothesis_key: str = "hypothesis",
    group_key: str = "accent_family",
) -> dict[str, Any]:
    if not rows:
        raise ValueError("eval rows cannot be empty")
    total_words, total_errors = 0, 0.0
    group_words: dict[str, int] = {}
    group_errors: dict[str, float] = {}
    for row in rows:
        ref, hyp = str(row[reference_key]), str(row[hypothesis_key])
        words = max(1, len(ref.split()))
        errors = wer(ref, hyp) * words
        group = str(row.get(group_key) or "unknown")
        total_words += words
        total_errors += errors
        group_words[group] = group_words.get(group, 0) + words
        group_errors[group] = group_errors.get(group, 0.0) + errors
    by_group = {group: group_errors[group] / group_words[group] for group in group_words}
    return {
        "utterances": len(rows),
        "wer": total_errors / total_words,
        "by_group": by_group,
        "parity": parity_gap(by_group, higher_is_better=False),
    }


def eval_nbest(
    rows: Sequence[Mapping[str, Any]],
    *,
    reference_key: str = "reference",
    nbest_key: str = "nbest",
    group_key: str = "accent_family",
) -> dict[str, Any]:
    if not rows:
        raise ValueError("eval rows cannot be empty")
    first, oracle = [], []
    for row in rows:
        nbest = row.get(nbest_key) or []
        if not nbest:
            raise ValueError("nbest row missing candidates")
        candidates = [str(item.get("text", item) if isinstance(item, Mapping) else item) for item in nbest]
        ref = str(row[reference_key])
        first.append({**row, "hypothesis": candidates[0]})
        oracle.append({**row, "hypothesis": min(candidates, key=lambda candidate: wer(ref, candidate))})
    first_report, oracle_report = eval_asr(first, reference_key=reference_key, group_key=group_key), eval_asr(
        oracle, reference_key=reference_key, group_key=group_key
    )
    return {
        "utterances": len(rows),
        "first_best_wer": first_report["wer"],
        "oracle_wer": oracle_report["wer"],
        "recoverable_gap": first_report["wer"] - oracle_report["wer"],
        "first_best_by_group": first_report["by_group"],
        "oracle_by_group": oracle_report["by_group"],
    }


def eval_repair(
    rows: Sequence[Mapping[str, Any]],
    *,
    reference_key: str = "reference_clean",
    hypothesis_key: str = "hypothesis_clean",
    group_key: str = "accent_family",
) -> dict[str, Any]:
    if not rows:
        raise ValueError("repair rows cannot be empty")
    clean = eval_asr(rows, reference_key=reference_key, hypothesis_key=hypothesis_key, group_key=group_key)
    total = len(rows)
    unsupported = sum(bool(row.get("unsupported_claims")) for row in rows)
    decisions = [
        (bool(row.get("should_clarify")), str(row.get("decision") or "answer") == "clarify")
        for row in rows
    ]
    correct_decisions = sum(should == did for should, did in decisions)
    useful_clarifications = sum(should and did for should, did in decisions)
    clarifications = sum(did for _, did in decisions)
    should_clarify = sum(should for should, _ in decisions)
    return {
        "utterances": total,
        "clean_wer": clean["wer"],
        "clean_by_group": clean["by_group"],
        "clean_parity": clean["parity"],
        "decision_accuracy": correct_decisions / total,
        "clarify_precision": useful_clarifications / clarifications if clarifications else 1.0,
        "clarify_recall": useful_clarifications / should_clarify if should_clarify else 1.0,
        "hallucination_rate": unsupported / total,
    }


def boundary_f1(
    reference: Sequence[int] | str,
    hypothesis: Sequence[int] | str,
    *,
    tolerance: int = 0,
) -> dict[str, float]:
    ref = _boundaries(reference)
    hyp = _boundaries(hypothesis)
    return _prf(_match_boundaries(ref, hyp, tolerance), len(hyp), len(ref))


def _match_boundaries(reference: Sequence[int], hypothesis: Sequence[int], tolerance: int) -> int:
    matched: set[int] = set()
    true_positive = 0
    for point in hypothesis:
        match = next((r for r in reference if r not in matched and abs(r - point) <= tolerance), None)
        if match is not None:
            matched.add(match)
            true_positive += 1
    return true_positive


def _prf(true_positive: int, hyp_count: int, ref_count: int) -> dict[str, float]:
    precision = true_positive / hyp_count if hyp_count else 1.0
    recall = true_positive / ref_count if ref_count else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": precision, "recall": recall, "f1": f1}


def _boundaries(value: Sequence[int] | str) -> list[int]:
    if isinstance(value, str):
        return [i for i, char in enumerate(value) if char in ".?!"]
    return sorted(int(item) for item in value)


def eval_segmentation(
    rows: Sequence[Mapping[str, Any]],
    *,
    reference_key: str = "reference",
    hypothesis_key: str = "hypothesis",
    group_key: str = "accent_family",
    tolerance: int = 0,
) -> dict[str, Any]:
    if not rows:
        raise ValueError("segmentation rows cannot be empty")
    tp = hyp_count = ref_count = 0
    punct_ok = punct_total = case_ok = case_total = 0
    cs_tp = cs_hyp = cs_ref = 0
    has_code_switch = False
    groups: dict[str, list[int]] = {}
    for row in rows:
        reference, hypothesis = str(row[reference_key]), str(row[hypothesis_key])
        ref_idx, hyp_idx = _sentence_boundaries(reference), _sentence_boundaries(hypothesis)
        matched = _match_boundaries(ref_idx, hyp_idx, tolerance)
        tp, hyp_count, ref_count = tp + matched, hyp_count + len(hyp_idx), ref_count + len(ref_idx)
        counts = groups.setdefault(str(row.get(group_key) or "unknown"), [0, 0, 0])
        counts[0] += matched
        counts[1] += len(hyp_idx)
        counts[2] += len(ref_idx)
        ref_words, hyp_words = _words_with_marks(reference), _words_with_marks(hypothesis)
        for i, (ref_core, ref_punct) in enumerate(ref_words):
            punct_total += 1
            case_total += 1
            if i < len(hyp_words):
                hyp_core, hyp_punct = hyp_words[i]
                punct_ok += ref_punct == hyp_punct
                case_ok += _first_upper(ref_core) == _first_upper(hyp_core)
        if "reference_switches" in row and "hypothesis_switches" in row:
            has_code_switch = True
            ref_switch = sorted(int(x) for x in row["reference_switches"])
            hyp_switch = sorted(int(x) for x in row["hypothesis_switches"])
            cs_tp += _match_boundaries(ref_switch, hyp_switch, tolerance)
            cs_hyp += len(hyp_switch)
            cs_ref += len(ref_switch)
    by_group = {group: _prf(c[0], c[1], c[2])["f1"] for group, c in groups.items()}
    report = {
        "utterances": len(rows),
        "boundary_f1": _prf(tp, hyp_count, ref_count)["f1"],
        "punctuation_accuracy": punct_ok / punct_total if punct_total else 1.0,
        "casing_accuracy": case_ok / case_total if case_total else 1.0,
        "by_group": by_group,
        "parity": parity_gap(by_group, higher_is_better=True),
    }
    if has_code_switch:
        report["code_switch_boundary_f1"] = _prf(cs_tp, cs_hyp, cs_ref)["f1"]
    return report


def _sentence_boundaries(text: str) -> list[int]:
    return [i for i, word in enumerate(text.split()) if word.rstrip().endswith((".", "?", "!"))]


def _words_with_marks(text: str) -> list[tuple[str, str]]:
    pairs = []
    for raw in text.split():
        core, punct = raw, ""
        while core and not core[-1].isalnum():
            punct = core[-1] + punct
            core = core[:-1]
        pairs.append((core, punct))
    return pairs


def _first_upper(core: str) -> bool:
    return bool(core) and core[0].isupper()


def route_stage_a(
    payload: Mapping[str, Any],
    *,
    min_confidence: float = 0.75,
    max_disagreement: float = 0.25,
) -> str:
    signals = payload.get("signals", {})
    confidence = float(signals.get("asr_confidence", 1.0))
    disagreement = float(signals.get("nbest_disagreement", 0.0))
    hard = (
        confidence < min_confidence
        or disagreement > max_disagreement
        or bool(signals.get("possible_code_switch"))
        or bool(signals.get("needs_hard_path"))
    )
    return "hard" if hard else "fast"


def release_gate(current: Mapping[str, float], previous: Mapping[str, float] | None = None) -> dict[str, Any]:
    failures = []
    previous = previous or {}
    lower_is_better = (
        "wer",
        "average_wer",
        "worst_group_wer",
        "parity_gap",
        "hallucination_rate",
        "rtf",
        "tokens_to_first_answer",
        "resident_memory_gb",
        "on_disk_mb",
    )
    higher_is_better = (
        "intent_accuracy",
        "worst_group_intent_accuracy",
        "clarify_precision",
        "clarify_recall",
        "boundary_f1",
        "code_switch_boundary_f1",
    )
    for key in lower_is_better:
        if key in current and key in previous and current[key] > previous[key]:
            failures.append(f"{key} regressed: {current[key]} > {previous[key]}")
    for key in higher_is_better:
        if key in current and key in previous and current[key] < previous[key]:
            failures.append(f"{key} regressed: {current[key]} < {previous[key]}")
    return {"passed": not failures, "failures": failures}


def phase_status(path: str | Path, metrics: Mapping[str, float] | None = None) -> dict[str, Any]:
    stats = ledger_stats(path)
    metrics = metrics or {}
    leaks = split_leaks(path)
    issues = ledger_issues(path)
    checks = {
        "phase_0_contract_loop": stats["experiments"] > 0,
        "phase_1_eval_seed": stats["eval_clips"] >= 10 or metrics.get("eval_utterances", 0) >= 10,
        "phase_1_repair_gate": "intent_accuracy" in metrics or "clean_wer" in metrics,
        "phase_2_data_gate": stats["train_hours"] > 0 and stats["coverage_cells"] > 0,
        "license_gate": not issues["license"],
        "defect_gate": not issues["defects"],
        "split_gate": not leaks,
        "runpod_ready": (
            stats["train_hours"] > 0
            and stats["eval_clips"] > 0
            and stats["experiments"] > 0
            and not leaks
            and not issues["license"]
            and not issues["defects"]
        ),
    }
    next_needed = [name for name, passed in checks.items() if not passed]
    return {"stats": stats, "checks": checks, "next_needed": next_needed}


def stable_bucket(value: str, *, salt: str = "babel") -> float:
    digest = hashlib.sha256(f"{salt}:{value}".encode()).hexdigest()[:16]
    return int(digest, 16) / float(16**16)


def assign_splits(
    path: str | Path,
    *,
    train: float = 0.8,
    dev: float = 0.1,
    test: float = 0.1,
    group_key: str = "auto",
    salt: str = "babel",
    overwrite: bool = False,
) -> dict[str, int]:
    if abs((train + dev + test) - 1.0) > 1e-9:
        raise ValueError("train + dev + test must equal 1")
    fields = ("clip_id", "speaker_hash", "source_id", "audio_hash", "split", "training_allowed", "eval_allowed")
    if group_key != "auto" and group_key not in CLIP_COLUMNS:
        raise ValueError(f"unknown split group key: {group_key}")
    init_ledger(path)
    with closing(sqlite3.connect(path)) as db, db:
        db.row_factory = sqlite3.Row
        rows = [dict(row) for row in db.execute(f"select {', '.join(fields)} from clips").fetchall()]
        counts = {"train": 0, "dev": 0, "test": 0, "skipped": 0}
        for row in rows:
            old_split = row.get("split")
            eligible = row.get("training_allowed") or row.get("eval_allowed")
            if not eligible or old_split == "quarantine" or (old_split not in (None, "", "unassigned") and not overwrite):
                counts["skipped"] += 1
                continue
            group = _split_group(row, group_key)
            bucket = stable_bucket(group, salt=salt)
            split = "train" if bucket < train else "dev" if bucket < train + dev else "test"
            db.execute("update clips set split = ? where clip_id = ?", [split, row["clip_id"]])
            counts[split] += 1
    return counts


def _split_group(row: Mapping[str, Any], group_key: str) -> str:
    if group_key != "auto":
        return str(row.get(group_key) or row["clip_id"])
    for key in ("speaker_hash", "source_id", "audio_hash", "clip_id"):
        if row.get(key):
            return str(row[key])
    return str(row["clip_id"])


def export_shard(
    path: str | Path,
    *,
    split: str | None = None,
    training_allowed: bool | None = None,
    eval_allowed: bool | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    clauses, values = [], []
    if split is not None:
        clauses.append("split = ?")
        values.append(split)
    if training_allowed is not None:
        clauses.append("coalesce(training_allowed, 0) = ?")
        values.append(int(training_allowed))
    if eval_allowed is not None:
        clauses.append("coalesce(eval_allowed, 0) = ?")
        values.append(int(eval_allowed))
    where = " where " + " and ".join(clauses) if clauses else ""
    sql = f"select * from clips{where} order by clip_id"
    if limit is not None:
        sql += " limit ?"
        values.append(limit)
    init_ledger(path)
    with closing(sqlite3.connect(path)) as db:
        db.row_factory = sqlite3.Row
        return [dict(row) for row in db.execute(sql, values).fetchall()]


def ledger_issues(path: str | Path) -> dict[str, list[dict[str, Any]]]:
    init_ledger(path)
    queries = {
        "license": """
            select clip_id, source_id, split, license_name, license_url, training_allowed, eval_allowed, notes
            from clips
            where (coalesce(training_allowed, 0) = 1 or coalesce(eval_allowed, 0) = 1)
              and (license_name is null or license_name = '')
        """,
        "defects": """
            select clip_id, source_id, split, noise_tier, training_allowed, eval_allowed, notes
            from clips
            where (coalesce(training_allowed, 0) = 1 or coalesce(eval_allowed, 0) = 1)
              and (noise_tier = 'defective' or notes like '%clipping%' or notes like '%near_silent%' or notes like '%low_sample_rate%')
        """,
        "unassigned_eligible": """
            select clip_id, source_id, split, training_allowed, eval_allowed, notes
            from clips
            where (coalesce(training_allowed, 0) = 1 or coalesce(eval_allowed, 0) = 1)
              and (split is null or split = '' or split = 'unassigned')
        """,
    }
    with closing(sqlite3.connect(path)) as db:
        db.row_factory = sqlite3.Row
        return {name: [dict(row) for row in db.execute(sql).fetchall()] for name, sql in queries.items()}


def audit(path: str | Path, metrics: Mapping[str, float] | None = None) -> dict[str, Any]:
    status = phase_status(path, metrics)
    issues = ledger_issues(path)
    leaks = split_leaks(path)
    failures = []
    for name, rows in issues.items():
        if rows and name != "unassigned_eligible":
            failures.append(f"{name}: {len(rows)}")
    if leaks:
        failures.append(f"split_leaks: {len(leaks)}")
    return {
        "passed": not failures,
        "failures": failures,
        "stats": status["stats"],
        "phase_checks": status["checks"],
        "issues": issues,
        "split_leaks": leaks,
    }


def markdown_report(
    path: str | Path,
    *,
    metrics: Mapping[str, float] | None = None,
    targets: Sequence[Mapping[str, Any]] | None = None,
) -> str:
    status = phase_status(path, metrics)
    cov = coverage(path)
    gaps = coverage_gaps(path, targets) if targets else []
    issues = ledger_issues(path)
    leaks = split_leaks(path)
    recent = experiments(path, 5)
    lines = [
        "# Babel Local Report",
        "",
        "## Stats",
        _kv(status["stats"]),
        "",
        "## Phase Gates",
        _kv(status["checks"]),
        "",
        "## Metrics",
        _kv(metrics or {}),
        "",
        "## Coverage",
        _table(cov[:20]),
        "",
        "## Coverage Gaps",
        _table(gaps[:20]),
        "",
        "## License Issues",
        _table(issues["license"][:20]),
        "",
        "## Defect Issues",
        _table(issues["defects"][:20]),
        "",
        "## Unassigned Eligible Clips",
        _table(issues["unassigned_eligible"][:20]),
        "",
        "## Split Leaks",
        _table(leaks[:20]),
        "",
        "## Recent Experiments",
        _table(recent),
    ]
    return "\n".join(lines).rstrip() + "\n"


def _kv(values: Mapping[str, Any]) -> str:
    return "\n".join(f"- **{key}:** {value}" for key, value in values.items()) or "- none"


def _table(rows: Sequence[Mapping[str, Any]]) -> str:
    if not rows:
        return "- none"
    keys = list(dict.fromkeys(key for row in rows for key in row))
    lines = ["| " + " | ".join(keys) + " |", "| " + " | ".join("---" for _ in keys) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(key, "")) for key in keys) + " |")
    return "\n".join(lines)


SCORECARD_METRICS = (
    ("average_wer", "Average WER"),
    ("worst_group_wer", "Worst-group WER"),
    ("parity_gap", "Parity gap"),
    ("intent_accuracy", "Intent accuracy"),
    ("worst_group_intent_accuracy", "Worst-group intent accuracy"),
    ("hallucination_rate", "Hallucination rate"),
    ("clarify_precision", "Clarify precision"),
    ("clarify_recall", "Clarify recall"),
    ("boundary_f1", "Boundary F1"),
    ("code_switch_boundary_f1", "Code-switch boundary F1"),
    ("rtf", "RTF"),
    ("tokens_to_first_answer", "Tokens-to-first-answer"),
    ("resident_memory_gb", "Resident memory (GB)"),
    ("on_disk_mb", "On-disk size (MB)"),
    ("license_clean_training_hours", "License-clean training hours"),
)


def scorecard(
    tiers: Mapping[str, Mapping[str, float]],
    previous: Mapping[str, float] | None = None,
) -> dict[str, Any]:
    columns = list(tiers)
    header = ["Metric", *columns] + (["Previous flagship"] if previous is not None else [])
    lines = ["| " + " | ".join(header) + " |", "| " + " | ".join("---" for _ in header) + " |"]
    for key, label in SCORECARD_METRICS:
        cells = [label]
        for column in columns:
            value = tiers[column].get(key)
            cells.append("" if value is None else str(value))
        if previous is not None:
            value = previous.get(key)
            cells.append("" if value is None else str(value))
        lines.append("| " + " | ".join(cells) + " |")
    gate = release_gate(tiers["flagship"], previous) if previous is not None and "flagship" in tiers else None
    return {"table": "\n".join(lines), "gate": gate}


def init_ledger(path: str | Path) -> Path:
    db_path = Path(path)
    columns = ", ".join(f"{name} {kind}" for name, kind in CLIP_COLUMNS.items())
    experiment_columns = ", ".join(f"{name} {kind}" for name, kind in EXPERIMENT_COLUMNS.items())
    with closing(sqlite3.connect(db_path)) as db, db:
        db.execute(f"create table if not exists clips ({columns})")
        db.execute(f"create table if not exists experiments ({experiment_columns})")
        db.execute("create index if not exists idx_clips_cell on clips(accent_family, fluency_tier, noise_tier)")
        db.execute("create index if not exists idx_clips_split on clips(split)")
    return db_path


def upsert_clip(path: str | Path, **row: Any) -> None:
    unknown = set(row) - set(CLIP_COLUMNS)
    if unknown:
        raise ValueError(f"unknown ledger fields: {', '.join(sorted(unknown))}")
    if "clip_id" not in row:
        raise ValueError("clip_id is required")
    init_ledger(path)
    names = list(row)
    placeholders = ", ".join("?" for _ in names)
    updates = ", ".join(f"{name}=excluded.{name}" for name in names if name != "clip_id")
    conflict = f"do update set {updates}" if updates else "do nothing"
    sql = (
        f"insert into clips ({', '.join(names)}) values ({placeholders}) "
        f"on conflict(clip_id) {conflict}"
    )
    with closing(sqlite3.connect(path)) as db, db:
        db.execute(sql, [row[name] for name in names])


def upsert_clips(path: str | Path, rows: Sequence[Mapping[str, Any]]) -> int:
    # ONE connection + one transaction + executemany per column-signature. The old per-row loop opened a
    # fresh connection + init_ledger + commit for EVERY row (~240 rows/s) and stalled for hours on the
    # network (fuseblk) volume for the 1M-row cycle upserts -- the exact hang we must not hit unattended.
    rows = [dict(r) for r in rows]
    if not rows:
        return 0
    for r in rows:                                            # same validation as upsert_clip()
        if "clip_id" not in r:
            raise ValueError("clip_id is required")
        unknown = set(r) - set(CLIP_COLUMNS)
        if unknown:
            raise ValueError(f"unknown ledger fields: {', '.join(sorted(unknown))}")
    init_ledger(path)
    groups: dict[tuple, list] = {}                            # group by present-column set for executemany
    for r in rows:
        names = tuple(r)
        groups.setdefault(names, []).append([r[n] for n in names])
    n = 0
    with closing(sqlite3.connect(path)) as db:
        db.execute("pragma synchronous=off")                 # ledger is rebuildable; trade durability for
        db.execute("pragma journal_mode=memory")             # speed so a 1M-row commit doesn't crawl on FUSE
        with db:
            for names, batch in groups.items():
                placeholders = ", ".join("?" for _ in names)
                updates = ", ".join(f"{nm}=excluded.{nm}" for nm in names if nm != "clip_id")
                conflict = f"do update set {updates}" if updates else "do nothing"
                sql = (f"insert into clips ({', '.join(names)}) values ({placeholders}) "
                       f"on conflict(clip_id) {conflict}")
                db.executemany(sql, batch)
                n += len(batch)
    return n


def coverage(path: str | Path, dims: Sequence[str] = ("accent_family", "fluency_tier", "noise_tier")) -> list[dict[str, Any]]:
    bad = set(dims) - set(CLIP_COLUMNS)
    if bad:
        raise ValueError(f"unknown coverage dimensions: {', '.join(sorted(bad))}")
    select = ", ".join(dims)
    sql = f"select {select}, count(*), coalesce(sum(duration_s), 0) / 3600 from clips group by {select}"
    with closing(sqlite3.connect(path)) as db:
        rows = db.execute(sql).fetchall()
    return [dict(zip((*dims, "clips", "hours"), row, strict=True)) for row in rows]


def coverage_entropy(
    path: str | Path,
    dims: Sequence[str] = ("accent_family", "fluency_tier", "noise_tier"),
) -> float:
    init_ledger(path)
    weights = [row["hours"] for row in coverage(path, dims) if row["hours"] > 0]
    total = sum(weights)
    if total <= 0 or len(weights) <= 1:
        return 0.0
    probs = [weight / total for weight in weights]
    return -sum(p * math.log(p) for p in probs) / math.log(len(weights))


def ledger_stats(path: str | Path) -> dict[str, Any]:
    init_ledger(path)
    with closing(sqlite3.connect(path)) as db:
        total_clips = db.execute("select count(*) from clips").fetchone()[0]
        train_hours = db.execute(
            "select coalesce(sum(duration_s), 0) / 3600 from clips where coalesce(training_allowed, 0) = 1"
        ).fetchone()[0]
        eval_clips = db.execute("select count(*) from clips where coalesce(eval_allowed, 0) = 1").fetchone()[0]
        coverage_cells = db.execute(
            """
            select count(*) from (
                select accent_family, fluency_tier, noise_tier
                from clips
                group by accent_family, fluency_tier, noise_tier
            )
            """
        ).fetchone()[0]
        experiments_count = db.execute("select count(*) from experiments").fetchone()[0]
    return {
        "clips": total_clips,
        "train_hours": train_hours,
        "eval_clips": eval_clips,
        "coverage_cells": coverage_cells,
        "coverage_entropy": coverage_entropy(path),
        "experiments": experiments_count,
    }


def coverage_gaps(
    path: str | Path,
    targets: Sequence[Mapping[str, Any]],
    *,
    dims: Sequence[str] = ("accent_family", "fluency_tier", "noise_tier"),
) -> list[dict[str, Any]]:
    have = {tuple(row.get(dim) for dim in dims): row["hours"] for row in coverage(path, dims)}
    gaps = []
    for target in targets:
        key = tuple(target.get(dim) for dim in dims)
        target_hours = float(target.get("target_hours", 0))
        current_hours = have.get(key, 0.0)
        if current_hours < target_hours:
            gaps.append(
                {
                    **{dim: target.get(dim) for dim in dims},
                    "hours": current_hours,
                    "gap_hours": target_hours - current_hours,
                }
            )
    return sorted(gaps, key=lambda row: row["gap_hours"], reverse=True)


def split_leaks(path: str | Path) -> list[dict[str, Any]]:
    sql = """
        select kind, value, group_concat(distinct split) as splits
        from (
            select 'audio_hash' as kind, audio_hash as value, split from clips where audio_hash is not null and split is not null
            union all
            select 'speaker_hash' as kind, speaker_hash as value, split from clips where speaker_hash is not null and split is not null
            union all
            select 'source_id' as kind, source_id as value, split from clips where source_id is not null and split is not null
        )
        group by kind, value
        having count(distinct split) > 1
    """
    init_ledger(path)
    with closing(sqlite3.connect(path)) as db:
        db.row_factory = sqlite3.Row
        return [dict(row) for row in db.execute(sql).fetchall()]


def review_queue(path: str | Path, limit: int = 20) -> list[dict[str, Any]]:
    sql = """
        select clip_id, source_id, accent_family, fluency_tier, noise_tier,
               teacher_agreement, cell_rarity, human_review_priority, notes
        from clips
        where coalesce(training_allowed, 0) = 1 or coalesce(eval_allowed, 0) = 1
        order by
            coalesce(human_review_priority, 0) desc,
            coalesce(cell_rarity, 0) desc,
            coalesce(teacher_agreement, 1) asc
        limit ?
    """
    with closing(sqlite3.connect(path)) as db:
        db.row_factory = sqlite3.Row
        return [dict(row) for row in db.execute(sql, [limit]).fetchall()]


def record_experiment(path: str | Path, **row: Any) -> None:
    unknown = set(row) - set(EXPERIMENT_COLUMNS)
    if unknown:
        raise ValueError(f"unknown experiment fields: {', '.join(sorted(unknown))}")
    if "experiment_id" not in row:
        raise ValueError("experiment_id is required")
    if "metrics_json" in row and not isinstance(row["metrics_json"], str):
        row["metrics_json"] = json.dumps(row["metrics_json"], sort_keys=True)
    init_ledger(path)
    names = list(row)
    placeholders = ", ".join("?" for _ in names)
    updates = ", ".join(f"{name}=excluded.{name}" for name in names if name != "experiment_id")
    conflict = f"do update set {updates}" if updates else "do nothing"
    sql = (
        f"insert into experiments ({', '.join(names)}) values ({placeholders}) "
        f"on conflict(experiment_id) {conflict}"
    )
    with closing(sqlite3.connect(path)) as db, db:
        db.execute(sql, [row[name] for name in names])


def experiments(path: str | Path, limit: int = 20) -> list[dict[str, Any]]:
    sql = """
        select experiment_id, created_at, hypothesis, component, data, metrics_json, decision, notes
        from experiments
        order by created_at desc, experiment_id desc
        limit ?
    """
    with closing(sqlite3.connect(path)) as db:
        db.row_factory = sqlite3.Row
        rows = [dict(row) for row in db.execute(sql, [limit]).fetchall()]
    for row in rows:
        if row.get("metrics_json"):
            row["metrics"] = json.loads(row.pop("metrics_json"))
    return rows
