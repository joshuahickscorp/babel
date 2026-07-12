from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any

_PUNCTUATION = re.compile(r"[^\w\s']")
_SPACE = re.compile(r"\s+")
_SPOKEN_PUNCTUATION = re.compile(
    r"\b(full stop|period|comma|colon|semicolon|forward slash|slash|dash|hyphen|"
    r"open parenthesis|close parenthesis|apostrophe|exclamation mark|question mark)\b",
    re.I,
)
_MEDICAL_PHRASE = re.compile(
    r"\b(mean arterial pressure|central venous pressure|blood pressure|"
    r"heart rate|respiratory rate|oxygen saturation)\b",
    re.I,
)


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "").casefold().strip()
    text = _PUNCTUATION.sub(" ", text)
    return _SPACE.sub(" ", text).strip()


def normalize_lenient_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "").casefold().strip()
    text = _SPOKEN_PUNCTUATION.sub(" ", text)
    text = text.replace("greater than", " ").replace("less than", " ").replace(" equals ", " ")
    text = _MEDICAL_PHRASE.sub(" ", text)
    text = _PUNCTUATION.sub(" ", text)
    return _SPACE.sub(" ", text).strip()


def normalize_words(text: str) -> list[str]:
    return normalize_text(text).split()


def edit_distance(reference: Sequence[Any], hypothesis: Sequence[Any]) -> int:
    row = list(range(len(hypothesis) + 1))
    for i, ref_item in enumerate(reference, 1):
        prev, row[0] = row[0], i
        for j, hyp_item in enumerate(hypothesis, 1):
            old = row[j]
            row[j] = min(row[j] + 1, row[j - 1] + 1, prev + (ref_item != hyp_item))
            prev = old
    return row[-1]


def wer(reference: str, hypothesis: str, *, normalize: bool = True) -> float:
    ref = normalize_words(reference) if normalize else reference.split()
    hyp = normalize_words(hypothesis) if normalize else hypothesis.split()
    if not ref:
        return 0.0 if not hyp else 1.0
    return edit_distance(ref, hyp) / len(ref)


def cer(reference: str, hypothesis: str, *, normalize: bool = True) -> float:
    ref_text = normalize_text(reference) if normalize else reference
    hyp_text = normalize_text(hypothesis) if normalize else hypothesis
    if not ref_text:
        return 0.0 if not hyp_text else 1.0
    return edit_distance(list(ref_text), list(hyp_text)) / len(ref_text)


def parity_gap(scores: Mapping[str, float], *, higher_is_better: bool = True) -> dict[str, Any]:
    if not scores:
        raise ValueError("scores cannot be empty")
    best = max(scores, key=scores.get) if higher_is_better else min(scores, key=scores.get)
    worst = min(scores, key=scores.get) if higher_is_better else max(scores, key=scores.get)
    return {"best": best, "worst": worst, "gap": abs(scores[best] - scores[worst])}


def group_mean(rows: Sequence[Mapping[str, Any]], group_key: str, score_key: str) -> dict[str, float]:
    groups: dict[str, list[float]] = {}
    for row in rows:
        groups.setdefault(str(row.get(group_key) or "unknown"), []).append(float(row[score_key]))
    ranked = sorted(groups.items(), key=lambda item: -sum(item[1]) / len(item[1]))
    return {group: round(sum(values) / len(values), 4) for group, values in ranked}


def score_pairs(pairs: Sequence[tuple[str, str, str]]) -> dict[str, Any]:
    per_group_refs: dict[str, list[str]] = defaultdict(list)
    per_group_hyps: dict[str, list[str]] = defaultdict(list)
    n_per_group: dict[str, int] = defaultdict(int)
    all_wers = []
    for group, ref, hyp in pairs:
        per_group_refs[group].append(ref)
        per_group_hyps[group].append(hyp)
        n_per_group[group] += 1
        all_wers.append(wer(ref, hyp))

    per_group_wer = {}
    for group in per_group_refs:
        refs = " ".join(normalize_text(ref) for ref in per_group_refs[group]).strip()
        hyps = " ".join(normalize_text(hyp) for hyp in per_group_hyps[group]).strip()
        per_group_wer[group] = round(wer(refs, hyps, normalize=False) if refs else 0.0, 4)

    worst = max(per_group_wer.values()) if per_group_wer else None
    best = min(per_group_wer.values()) if per_group_wer else None
    avg = round(sum(all_wers) / len(all_wers), 4) if all_wers else None
    return {
        "average_wer": avg,
        "worst_group_wer": round(worst, 4) if worst is not None else None,
        "min_max_gap": round(worst - best, 4) if worst is not None else None,
        "per_group_wer": per_group_wer,
        "n_clips_per_group": dict(n_per_group),
    }


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
    first_report = eval_asr(first, reference_key=reference_key, group_key=group_key)
    oracle_report = eval_asr(oracle, reference_key=reference_key, group_key=group_key)
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


def _match_boundaries(reference: Sequence[int], hypothesis: Sequence[int], tolerance: int) -> int:
    matched: set[int] = set()
    true_positive = 0
    for point in hypothesis:
        match = next((ref for ref in reference if ref not in matched and abs(ref - point) <= tolerance), None)
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
