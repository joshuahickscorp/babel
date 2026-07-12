from __future__ import annotations

import json
from collections.abc import Mapping
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
        payload = _load_json(file)
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


def _load_json(path: str | Path) -> Any:
    with Path(path).open() as file:
        return json.load(file)
