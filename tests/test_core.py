import contextlib
import io
import importlib.util
import json
import math
import struct
import tempfile
import unittest
import wave
from pathlib import Path

from babel import (
    acquisition_plan,
    assign_splits,
    audit,
    benchmark_freeze,
    boundary_f1,
    cer,
    compute_preflight,
    coverage,
    coverage_entropy,
    coverage_gaps,
    eval_asr,
    eval_nbest,
    eval_repair,
    eval_segmentation,
    export_shard,
    experiments,
    group_dro_schedule,
    inspect_wav,
    init_ledger,
    iter_jsonl,
    ledger_stats,
    ledger_issues,
    manifest_wavs,
    markdown_report,
    normalize_words,
    parity_gap,
    phase_status,
    quality_cards,
    record_experiment,
    release_gate,
    repair_hygiene,
    repair_quality_cards,
    review_queue,
    route_stage_a,
    run_cycle_receipt,
    scorecard,
    split_leaks,
    stable_bucket,
    studio_distillation_plan,
    upsert_clip,
    upsert_clips,
    validate_dir,
    validate_acquisition_intake,
    validate_experiment_receipts,
    validate_stage,
    worst_cell_plan,
    wer,
)
from babel.cli import main


STAGE_A_EXAMPLE = {
    "schema_version": "babel.stage_a.v0",
    "audio": {"source_id": "clip_1", "sample_rate_hz": 16000, "duration_s": 3.42, "channels": 1},
    "decode": {"model_id": "stage-a-baseline", "tier": "flagship", "beam_size": 5, "temperature": 0.0, "rtf": 0.34},
    "literal": "i went to the pharmacy but they dont have my medicine innit",
    "nbest": [
        {"rank": 1, "text": "i went to the pharmacy but they dont have my medicine innit", "score": -0.41},
        {"rank": 2, "text": "i went to the pharmacy but they don't have my medicine in it", "score": -0.55},
    ],
    "segments": [{"start_s": 0.0, "end_s": 3.42, "text": "i went to the pharmacy", "lang": "en", "confidence": 0.72}],
    "signals": {"asr_confidence": 0.72, "nbest_disagreement": 0.31, "possible_code_switch": False, "needs_hard_path": True},
}

STAGE_B_ANSWER = {
    "schema_version": "babel.stage_b.v0",
    "source_id": "clip_1",
    "cleaned": "I went to the pharmacy, but they don't have my medicine.",
    "preserved_literal": "I went to the pharmacy, but they don't have my medicine, innit?",
    "intent": {"type": "statement", "summary": "Medicine unavailable.", "entities": [{"text": "pharmacy", "type": "place_generic", "confidence": 0.86}]},
    "languages": [{"lang": "en", "span": [0, 56], "confidence": 0.96}],
    "faithfulness": {"faithful": True, "risk": "low", "unsupported_claims": []},
    "decision": {"action": "answer", "clarifying_question": None},
    "confidence": {"overall": 0.81, "intent": 0.84, "entities": 0.78},
}

STAGE_B_CLARIFY = {
    "schema_version": "babel.stage_b.v0",
    "source_id": "clip_42",
    "cleaned": None,
    "preserved_literal": "can you book it for four or for fourteen",
    "intent": None,
    "faithfulness": {"faithful": False, "risk": "ambiguous_audio", "unsupported_claims": []},
    "decision": {"action": "clarify", "clarifying_question": "Did you mean four or fourteen?"},
    "confidence": {"overall": 0.42, "intent": 0.39, "entities": 0.31},
}


def clip(clip_id, duration_s, accent_family, priority=0.0):
    return {
        "clip_id": clip_id,
        "duration_s": duration_s,
        "accent_family": accent_family,
        "fluency_tier": "fluent",
        "noise_tier": "phone",
        "training_allowed": 1,
        "human_review_priority": priority,
    }


def write_tone(path, sample_rate=16000, frames=1600, amplitude=8000):
    samples = [
        int(amplitude * math.sin(2 * math.pi * 440 * i / sample_rate))
        for i in range(frames)
    ]
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(b"".join(struct.pack("<h", sample) for sample in samples))


class CoreTests(unittest.TestCase):
    def test_wer(self):
        self.assertEqual(wer("book it for four", "book it for four"), 0)
        self.assertAlmostEqual(wer("book it for four", "book it for fourteen"), 0.25)
        self.assertEqual(wer("Book, it for four!", "book it for four"), 0)
        self.assertEqual(normalize_words("Book, it!"), ["book", "it"])
        self.assertLess(cer("four", "for"), 1)

    def test_parity_gap_for_error_metric(self):
        gap = parity_gap({"clean_us": 0.03, "jamaican": 0.20}, higher_is_better=False)
        self.assertEqual(gap["best"], "clean_us")
        self.assertEqual(gap["worst"], "jamaican")
        self.assertAlmostEqual(gap["gap"], 0.17)

    def test_validate_stage_accepts_full_examples(self):
        self.assertIs(validate_stage(STAGE_A_EXAMPLE, "stage_a"), STAGE_A_EXAMPLE)
        self.assertIs(validate_stage(STAGE_B_ANSWER, "stage_b"), STAGE_B_ANSWER)
        self.assertIs(validate_stage(STAGE_B_CLARIFY, "stage_b"), STAGE_B_CLARIFY)
        self.assertEqual(route_stage_a(STAGE_A_EXAMPLE), "hard")

    def test_validate_stage_rejects_structural_errors(self):
        with self.assertRaises(ValueError):  # empty dicts no longer satisfy stage_b
            validate_stage({"schema_version": "babel.stage_b.v0", "source_id": "c", "faithfulness": {}, "decision": {}, "confidence": {}, "preserved_literal": "x"}, "stage_b")
        with self.assertRaises(ValueError):  # confidence out of [0,1]
            validate_stage({**STAGE_B_ANSWER, "confidence": {"overall": 1.4}}, "stage_b")
        with self.assertRaises(ValueError):  # answer needs cleaned text + intent
            validate_stage({**STAGE_B_ANSWER, "cleaned": None}, "stage_b")
        with self.assertRaises(ValueError):  # clarify needs a question
            validate_stage({**STAGE_B_CLARIFY, "decision": {"action": "clarify", "clarifying_question": None}}, "stage_b")
        with self.assertRaises(ValueError):  # bad decision enum
            validate_stage({**STAGE_B_ANSWER, "decision": {"action": "guess"}}, "stage_b")
        with self.assertRaises(ValueError):  # nbest ranks must ascend
            validate_stage({**STAGE_A_EXAMPLE, "nbest": [{"rank": 2, "text": "a", "score": -0.1}, {"rank": 1, "text": "b", "score": -0.2}]}, "stage_a")
        with self.assertRaises(ValueError):  # segment end before start
            validate_stage({**STAGE_A_EXAMPLE, "segments": [{"start_s": 2.0, "end_s": 1.0, "text": "x", "lang": "en"}]}, "stage_a")

    def test_validate_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "good.json").write_text(json.dumps(STAGE_B_ANSWER))
            (root / "bad.json").write_text(json.dumps({"schema_version": "babel.stage_b.v0", "source_id": "c"}))
            (root / "unknown.json").write_text(json.dumps({"schema_version": "babel.other.v0"}))
            result = validate_dir(root)
            self.assertEqual(result["checked"], 3)
            self.assertEqual(result["passed"], 1)

    def test_ledger_coverage(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "ledger.sqlite"
            init_ledger(db)
            upsert_clip(db, **clip("c1", 180, "caribbean", priority=0.9))
            self.assertEqual(
                coverage(db),
                [
                    {
                        "accent_family": "caribbean",
                        "fluency_tier": "fluent",
                        "noise_tier": "phone",
                        "clips": 1,
                        "hours": 0.05,
                    }
                ],
            )

    def test_jsonl_upsert_and_review_queue(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "ledger.sqlite"
            jsonl = root / "clips.jsonl"
            rows = [clip("c1", 30, "caribbean", priority=0.1), clip("c2", 30, "african", priority=0.9)]
            jsonl.write_text("\n".join(json.dumps(row) for row in rows))
            self.assertEqual(upsert_clips(db, iter_jsonl(jsonl)), 2)
            self.assertEqual(review_queue(db, 1)[0]["clip_id"], "c2")

    def test_eval_asr(self):
        report = eval_asr(
            [
                {"reference": "book it for four", "hypothesis": "book it for four", "accent_family": "clean_us"},
                {
                    "reference": "book it for four",
                    "hypothesis": "book it for fourteen",
                    "accent_family": "caribbean",
                },
            ]
        )
        self.assertAlmostEqual(report["wer"], 0.125)
        self.assertEqual(report["parity"]["worst"], "caribbean")

    def test_eval_nbest_oracle_gap(self):
        report = eval_nbest(
            [
                {
                    "reference": "book it for four",
                    "nbest": ["book it for fourteen", "book it for four"],
                    "accent_family": "caribbean",
                }
            ]
        )
        self.assertAlmostEqual(report["first_best_wer"], 0.25)
        self.assertEqual(report["oracle_wer"], 0)
        self.assertAlmostEqual(report["recoverable_gap"], 0.25)

    def test_eval_repair(self):
        report = eval_repair(
            [
                {
                    "reference_clean": "I need to go to the hospital.",
                    "hypothesis_clean": "I need to go to hospital.",
                    "decision": "answer",
                    "should_clarify": False,
                    "accent_family": "south_asian",
                },
                {
                    "reference_clean": "",
                    "hypothesis_clean": "",
                    "decision": "clarify",
                    "should_clarify": True,
                    "unsupported_claims": ["fourteen"],
                    "accent_family": "caribbean",
                },
            ]
        )
        self.assertEqual(report["decision_accuracy"], 1)
        self.assertEqual(report["clarify_precision"], 1)
        self.assertEqual(report["clarify_recall"], 1)
        self.assertEqual(report["hallucination_rate"], 0.5)

    def test_boundary_f1(self):
        self.assertEqual(boundary_f1("Hi. Go?", "Hi. Go?")["f1"], 1)
        self.assertLess(boundary_f1([2, 5], [2])["f1"], 1)

    def test_eval_segmentation(self):
        report = eval_segmentation(
            [
                {"reference": "I went home. Are you OK?", "hypothesis": "i went home are you ok", "accent_family": "british_isles"},
                {"reference": "Yes. No.", "hypothesis": "Yes. No.", "accent_family": "clean_us"},
            ]
        )
        self.assertAlmostEqual(report["boundary_f1"], 2 / 3)  # micro: recall 0.5, precision 1.0
        self.assertEqual(report["by_group"]["british_isles"], 0.0)  # no punctuation recovered
        self.assertLess(report["casing_accuracy"], 1.0)
        self.assertEqual(report["by_group"]["clean_us"], 1.0)
        self.assertEqual(report["parity"]["worst"], "british_isles")

    def test_eval_segmentation_code_switch(self):
        report = eval_segmentation(
            [{"reference": "move la cita", "hypothesis": "move la cita", "reference_switches": [1, 2], "hypothesis_switches": [1]}]
        )
        self.assertAlmostEqual(report["code_switch_boundary_f1"], 2 / 3)

    def test_coverage_entropy(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "ledger.sqlite"
            self.assertEqual(coverage_entropy(db), 0.0)
            upsert_clip(db, **clip("a", 3600, "caribbean"))
            self.assertEqual(coverage_entropy(db), 0.0)  # single cell
            upsert_clip(db, **clip("b", 3600, "african"))
            self.assertAlmostEqual(coverage_entropy(db), 1.0)  # two even cells
            self.assertIn("coverage_entropy", ledger_stats(db))

    def test_scorecard(self):
        result = scorecard(
            {"flagship": {"worst_group_wer": 0.18, "average_wer": 0.07}},
            {"worst_group_wer": 0.2, "average_wer": 0.08},
        )
        self.assertIn("Worst-group WER", result["table"])
        self.assertIn("Previous flagship", result["table"])
        self.assertTrue(result["gate"]["passed"])  # both WERs improved
        regressed = scorecard({"flagship": {"worst_group_wer": 0.25}}, {"worst_group_wer": 0.2})
        self.assertFalse(regressed["gate"]["passed"])  # worst-group regressed

    def test_route_stage_a(self):
        payload = {
            "schema_version": "babel.stage_a.v0",
            "audio": {},
            "decode": {},
            "literal": "",
            "nbest": [],
            "segments": [],
            "signals": {"asr_confidence": 0.4, "nbest_disagreement": 0.1},
        }
        self.assertEqual(route_stage_a(payload), "hard")

    def test_release_gate(self):
        result = release_gate(
            {"worst_group_wer": 0.21, "intent_accuracy": 0.8},
            {"worst_group_wer": 0.2, "intent_accuracy": 0.82},
        )
        self.assertFalse(result["passed"])
        self.assertEqual(len(result["failures"]), 2)

    def test_inspect_wav(self):
        with tempfile.TemporaryDirectory() as tmp:
            wav_path = Path(tmp) / "tone.wav"
            write_tone(wav_path)
            info = inspect_wav(wav_path)
            self.assertAlmostEqual(info["duration_s"], 0.1)
            self.assertEqual(info["sample_rate_hz"], 16000)
            self.assertEqual(info["flags"], [])

    def test_manifest_wavs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_tone(root / "tone.wav")
            rows = manifest_wavs(root, license_name="CC0", training_allowed=True)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["license_name"], "CC0")
            self.assertEqual(rows[0]["training_allowed"], 1)
            self.assertEqual(rows[0]["split"], "unassigned")
            rows = manifest_wavs(root, training_allowed=True)
            self.assertEqual(rows[0]["training_allowed"], 0)
            self.assertEqual(rows[0]["split"], "quarantine")
            self.assertIn("license_missing", rows[0]["notes"])

    def test_experiment_ledger(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "ledger.sqlite"
            record_experiment(
                db,
                experiment_id="E01",
                hypothesis="N-best helps hard cells",
                component="repair",
                metrics_json={"worst_group_wer": 0.2},
                decision="keep",
            )
            rows = experiments(db)
            self.assertEqual(rows[0]["experiment_id"], "E01")
            self.assertEqual(rows[0]["metrics"], {"worst_group_wer": 0.2})

    def test_run_cycle_receipt_records_required_proof(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "ledger.sqlite"
            receipt = Path(tmp) / "receipt.json"
            result = run_cycle_receipt(
                db,
                experiment_id="cycle_01",
                metrics={"average_wer": 0.4, "by_accent_family": {"caribbean": 0.2, "igbo": 0.5}},
                previous_metrics={"average_wer": 0.3, "worst_group_wer": 0.4, "parity_gap": 0.1},
                exact_command="babel run-cycle fixture",
                component="acoustic_distillation_scout",
                hypothesis="Scout must beat tiny on the worst group before release.",
                split="held_out eval",
                license_summary={"summary": "CC0 test fixture"},
                heldout_rows=[
                    {
                        "clip_id": "c1",
                        "accent_family": "caribbean",
                        "reference": "a b",
                        "hypothesis": "a",
                        "wer": 0.5,
                    },
                    {
                        "clip_id": "c2",
                        "accent_family": "igbo",
                        "reference": "a b c",
                        "hypothesis": "x y z",
                        "wer": 1.0,
                    },
                ],
                commit="abc123",
                workspace_dirty=True,
                output_receipt=receipt,
            )
            self.assertFalse(result["release_gate"]["passed"])
            self.assertEqual(result["worst_group_wer"], 0.5)
            self.assertAlmostEqual(result["parity_gap"], 0.3)
            self.assertEqual(result["failure_example"]["clip_id"], "c2")
            row = experiments(db)[0]
            self.assertEqual(row["experiment_id"], "cycle_01")
            self.assertEqual(row["metrics"]["worst_group_wer"], 0.5)
            saved = json.loads(receipt.read_text())
            self.assertEqual(saved["metrics_json"]["release_gate_passed"], False)

    def test_validate_experiment_receipts_enforces_model_evidence_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            good = Path(tmp) / "good.json"
            bad = Path(tmp) / "bad.json"
            good.write_text(
                json.dumps(
                    {
                        "experiment_id": "E01",
                        "component": "acoustic_distillation_scout",
                        "hypothesis": "Worst group must improve.",
                        "decision": "reject_for_release_gate_regression",
                        "data": json.dumps(
                            {
                                "exact_command": "babel train",
                                "commit": "abc123",
                                "workspace_dirty_at_recording": True,
                                "split": "eval",
                                "license_summary": {"summary": "CC0"},
                                "per_group_table_key": "metrics_json.by_accent_family",
                                "release_gate_decision": {"passed": False, "failures": ["regressed"]},
                                "failure_example": {
                                    "clip_id": "c1",
                                    "reference": "hello world",
                                    "hypothesis": "hello",
                                    "wer": 0.5,
                                },
                            }
                        ),
                        "metrics_json": {
                            "worst_group_wer": 0.5,
                            "parity_gap": 0.3,
                            "by_accent_family": {"igbo": 0.5},
                            "release_gate_passed": False,
                        },
                    }
                )
            )
            bad.write_text(
                json.dumps(
                    {
                        "experiment_id": "E02",
                        "component": "acoustic_distillation_scout",
                        "hypothesis": "Incomplete claim.",
                        "decision": "keep",
                        "data": json.dumps({"exact_command": "babel train"}),
                        "metrics_json": {"average_wer": 0.1},
                    }
                )
            )
            report = validate_experiment_receipts([good, bad])
            self.assertFalse(report["passed"])
            self.assertTrue(report["results"][0]["passed"])
            self.assertIn("missing metrics_json.worst_group_wer", report["results"][1]["failures"])
            self.assertIn("missing non-empty data.failure_example", report["results"][1]["failures"])

    def test_validate_experiment_receipts_accepts_contract_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            receipt = Path(tmp) / "contract.json"
            receipt.write_text(
                json.dumps(
                    {
                        "experiment_id": "E03",
                        "component": "segmentation_contract",
                        "hypothesis": "Boundary restoration must remain measurable separately from ASR WER.",
                        "decision": "record_as_contract_evidence",
                        "data": json.dumps(
                            {
                                "exact_command": "babel eval-segmentation eval/segmentation_eval.jsonl",
                                "commit": "abc123",
                                "workspace_dirty_at_recording": True,
                                "split": "text fixture contract seed",
                                "license_summary": {"summary": "text-only fixture"},
                                "contract_metric_key": "metrics_json.boundary_f1",
                                "per_group_table_key": "metrics_json.by_accent_family",
                                "failure_example": {
                                    "reference": "I went home. Are you OK?",
                                    "hypothesis": "i went home are you ok",
                                    "score": 0.0,
                                },
                            }
                        ),
                        "metrics_json": {
                            "boundary_f1": 0.5,
                            "parity_gap": 1.0,
                            "by_accent_family": {"british_isles": 0.0, "clean_us": 1.0},
                        },
                    }
                )
            )
            report = validate_experiment_receipts([receipt])
            self.assertTrue(report["passed"])
            self.assertEqual(report["results"][0]["scope"], "contract_evidence")

    def test_gaps_leaks_phase_and_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "ledger.sqlite"
            rows = [
                {
                    **clip("train", 3600, "caribbean"),
                    "eval_allowed": 1,
                    "split": "train",
                    "audio_hash": "same",
                    "source_id": "s1",
                },
                {
                    **clip("eval", 60, "caribbean"),
                    "eval_allowed": 1,
                    "split": "test",
                    "audio_hash": "same",
                    "source_id": "s2",
                },
            ]
            upsert_clips(db, rows)
            record_experiment(db, experiment_id="E01", metrics_json={"intent_accuracy": 0.9})
            self.assertTrue(phase_status(db)["checks"]["phase_1_repair_gate"])
            targets = [
                {
                    "accent_family": "caribbean",
                    "fluency_tier": "fluent",
                    "noise_tier": "phone",
                    "target_hours": 2,
                }
            ]
            self.assertEqual(ledger_stats(db)["coverage_cells"], 1)
            self.assertAlmostEqual(coverage_gaps(db, targets)[0]["gap_hours"], 59 / 60)
            self.assertEqual(split_leaks(db)[0]["kind"], "audio_hash")
            status = phase_status(db, {"intent_accuracy": 0.9, "eval_utterances": 10})
            self.assertFalse(status["checks"]["runpod_ready"])
            report = markdown_report(db, metrics={"intent_accuracy": 0.9})
            self.assertIn("# Babel Local Report", report)
            self.assertIn("## License Issues", report)

    def test_worst_cell_plan_prioritizes_weak_undercovered_groups(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "ledger.sqlite"
            upsert_clips(
                db,
                [
                    {**clip("a1", 7200, "caribbean"), "eval_allowed": 1},
                    {**clip("b1", 1800, "igbo"), "eval_allowed": 0},
                ],
            )
            plan = worst_cell_plan(
                db,
                {"by_accent_family": {"caribbean": 0.2, "igbo": 0.8}},
                target_hours=2,
                target_eval_clips=1,
            )
            self.assertEqual(plan[0]["accent_family"], "igbo")
            self.assertEqual(plan[0]["recommended_action"], "acquire_or_license_training_audio")
            self.assertGreater(plan[0]["priority"], plan[1]["priority"])

    def test_group_dro_schedule_weights_worst_groups_but_blocks_zero_hour_cells(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "ledger.sqlite"
            upsert_clips(
                db,
                [
                    {**clip("caribbean-a", 7200, "caribbean"), "training_allowed": 1, "eval_allowed": 1},
                    {**clip("igbo-eval", 60, "igbo"), "training_allowed": 0, "eval_allowed": 1},
                ],
            )
            worst = Path(tmp) / "worst.json"
            worst.write_text(
                json.dumps(
                    {
                        "rows": [
                            {
                                "rank": 1,
                                "accent_family": "igbo",
                                "group_metric": 0.8,
                                "train_hours": 0.0,
                                "eval_clips": 1,
                            }
                        ]
                    }
                )
            )
            schedule = group_dro_schedule(
                db,
                metrics={
                    "worst_group_wer": 0.8,
                    "parity_gap": 0.6,
                    "by_accent_family": {"caribbean": 0.2, "igbo": 0.8},
                },
                worst_cell_plan_receipt=worst,
                target_hours=2,
                target_eval_clips=1,
                top_groups=2,
            )
            self.assertEqual(schedule["status"], "blocked")
            self.assertIn("group_dro_selected_groups_have_zero_training_hours", schedule["blockers"])
            self.assertIn("group_dro_exact_training_command_not_recorded", schedule["blockers"])
            self.assertEqual(schedule["rows"][0]["accent_family"], "igbo")
            self.assertGreater(schedule["rows"][0]["sampler_weight"], schedule["rows"][1]["sampler_weight"])
            self.assertEqual(schedule["rows"][0]["recommended_action"], "block_group_dro_until_training_audio_exists")
            self.assertIn("sampler weights by accent_family", schedule["required_training_receipt_fields"])

    def test_acquisition_plan_targets_zero_hour_cells_with_license_gates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "ledger.sqlite"
            init_ledger(db)
            schedule = root / "schedule.json"
            schedule.write_text(
                json.dumps(
                    {
                        "rows": [
                            {
                                "rank": 1,
                                "accent_family": "luganda",
                                "current_group_wer": 8.5,
                                "sampler_weight": 4.0,
                                "train_hours": 0.0,
                                "eval_gap": 0,
                                "recommended_action": "block_group_dro_until_training_audio_exists",
                            }
                        ]
                    }
                )
            )
            manifest = root / "manifest.csv"
            manifest.write_text(
                "clip_id,source,license,redistributable,clip_sha256\n"
                "eval-1,afrispeech-200,CC-BY-NC-SA-4.0,no,abc123\n"
            )
            receipt = root / "acquire.json"
            plan = acquisition_plan(
                db,
                schedule_receipt=schedule,
                manifest_csv=manifest,
                target_hours=10,
                output_receipt=receipt,
            )
            self.assertEqual(plan["status"], "plan_only_no_download_or_training")
            self.assertEqual(plan["do_not_train_manifest_hashes"]["count"], 1)
            self.assertEqual(plan["targets"][0]["accent_family"], "luganda")
            self.assertEqual(plan["targets"][0]["hours_to_acquire"], 10.0)
            self.assertIn("audio_hash", plan["targets"][0]["provenance_gate"]["required_clip_fields"])
            self.assertIn("afrispeech-200", plan["blocked_sources"][0]["source"])
            self.assertTrue(any("EdACC" in source["source"] for source in plan["allowed_sources"]))
            self.assertTrue(receipt.exists())

    def test_validate_acquisition_intake_enforces_source_license_and_hash_gates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = root / "plan.json"
            plan.write_text(
                json.dumps(
                    {
                        "allowed_sources": [
                            {"source": "EdACC current deposits 10283/8983"},
                            {"source": "SLR70"},
                        ],
                        "blocked_sources": [{"source": "afrispeech-200"}],
                        "targets": [{"accent_family": "luganda"}],
                    }
                )
            )
            manifest = root / "manifest.csv"
            manifest.write_text("clip_id,clip_sha256,source,redistributable\nm1,hash-eval,afrispeech-200,no\n")
            rows = [
                {
                    **clip("good", 60, "luganda"),
                    "source_id": "edacc-10283-speaker-a",
                    "source_url": "https://example.org/edacc/10283/good.wav",
                    "source_type": "EdACC current deposit 10283",
                    "license_name": "CC-BY-4.0",
                    "license_url": "https://creativecommons.org/licenses/by/4.0/",
                    "attribution": "Fixture speaker, EdACC 10283",
                    "audio_hash": "hash-new",
                    "speaker_hash": "speaker-a",
                    "split": "train",
                    "training_allowed": 1,
                    "redistribution_allowed": 1,
                    "pii_status": "clean",
                },
                {
                    **clip("bad", 60, "luganda"),
                    "source_id": "afrispeech-200-eval-bad",
                    "source_url": "https://example.org/afrispeech/bad.wav",
                    "source_type": "afrispeech-200",
                    "license_name": "CC-BY-NC-SA-4.0",
                    "license_url": "https://creativecommons.org/licenses/by-nc-sa/4.0/",
                    "attribution": "AfriSpeech",
                    "audio_hash": "hash-eval",
                    "speaker_hash": "speaker-b",
                    "split": "train",
                    "training_allowed": 1,
                    "redistribution_allowed": 0,
                    "pii_status": "clean",
                },
            ]
            receipt = root / "intake.json"
            result = validate_acquisition_intake(
                rows,
                acquisition_plan_receipt=plan,
                manifest_csv=manifest,
                output_receipt=receipt,
            )
            self.assertFalse(result["passed"])
            self.assertEqual(result["accepted"], 1)
            self.assertEqual(result["rejected"], 1)
            self.assertIn("source is blocked by acquisition plan", result["failures"])
            self.assertIn("audio_hash matches frozen benchmark manifest", result["failures"])
            self.assertAlmostEqual(result["accepted_hours_by_accent_family"]["luganda"], round(1 / 60, 6))
            self.assertTrue(receipt.exists())

    def test_benchmark_freeze_records_manifest_scorer_and_label_constraints(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = root / "manifest.csv"
            manifest.write_text(
                "clip_id,source,source_clip_ref,license,redistributable,attribution,accent_family,"
                "split,duration_s,reference_text,clip_sha256\n"
                "c1,afrispeech-200,c1,CC-BY-NC-SA-4.0,no,attr,luganda,eval,1.0,hello,hash1\n"
                "c2,afrispeech-200,c2,CC-BY-NC-SA-4.0,no,attr,igbo and yoruba,eval,1.0,hello,hash2\n"
            )
            scorer = root / "score.py"
            scorer.write_text("SCORER_VERSION = 'test-version'\nraise NotImplementedError('stub')\n")
            governance = root / "GOVERNANCE.md"
            governance.write_text("worst-group WER\n")
            losses = root / "babel_loses_here.md"
            losses.write_text("Babel loses here\n")
            receipt = root / "freeze.json"
            result = benchmark_freeze(
                manifest_csv=manifest,
                scorer_py=scorer,
                governance_md=governance,
                losses_md=losses,
                output_receipt=receipt,
            )
            self.assertTrue(result["passed"])
            self.assertEqual(result["manifest"]["rows"], 2)
            self.assertEqual(result["manifest"]["do_not_train_hashes"], 2)
            self.assertEqual(result["scorer"]["scorer_version"], "test-version")
            self.assertEqual(result["scorer"]["r3_inference_backend_status"], "stubbed")
            self.assertIn("luganda", result["low_n_groups"])
            self.assertIn("igbo and yoruba", result["label_review_groups"])
            self.assertTrue(receipt.exists())

            scorer.write_text("SCORER_VERSION = 'implemented-version'\ndef transcribe_with_model():\n    return {}\n")
            implemented = benchmark_freeze(
                manifest_csv=manifest,
                scorer_py=scorer,
                governance_md=governance,
                losses_md=losses,
            )
            self.assertEqual(implemented["scorer"]["r3_inference_backend_status"], "implemented")

    def test_benchmark_scorer_model_backend_helpers_remain_lightweight(self):
        score_path = Path(__file__).resolve().parents[1] / "benchmark" / "score.py"
        spec = importlib.util.spec_from_file_location("babel_benchmark_score", score_path)
        self.assertIsNotNone(spec)
        module = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(module)

        self.assertEqual(
            module.audio_path_for_row(Path("audio"), {"clip_id": "clip-1"}),
            Path("audio") / "clip-1.wav",
        )
        metrics = module.score_pairs(
            [
                ("luganda", "hello world", "hello"),
                ("english", "book it", "book it"),
            ]
        )
        self.assertEqual(metrics["worst_group_wer"], 0.5)
        self.assertEqual(metrics["min_max_gap"], 0.5)
        self.assertEqual(module.SCORER_VERSION, "0.2.0-model-backend")

    def test_compute_preflight_gates_disk_phase_and_receipts(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "ledger.sqlite"
            receipt = Path(tmp) / "receipt.json"
            receipt.write_text("{}")
            upsert_clips(
                db,
                [
                    {
                        **clip("c1", 3600, "caribbean"),
                        "license_name": "CC0",
                        "source_id": "s1",
                        "audio_hash": "a1",
                        "split": "train",
                        "eval_allowed": 1,
                    }
                ],
            )
            record_experiment(db, experiment_id="E01", metrics_json={"clean_wer": 0.1, "eval_utterances": 10})
            result = compute_preflight(
                db,
                workspace=tmp,
                min_free_gb=0,
                require_receipts=[receipt],
            )
            self.assertTrue(result["passed"])
            self.assertTrue(result["checks"]["disk_gate"])
            self.assertTrue(result["checks"]["required_receipts_gate"])
            blocked = compute_preflight(
                db,
                workspace=tmp,
                min_free_gb=0,
                require_receipts=[Path(tmp) / "missing.json"],
            )
            self.assertFalse(blocked["passed"])
            self.assertIn("required_receipts_gate", blocked["blockers"])

    def test_studio_distillation_plan_binds_preflight_worst_cells_and_receipts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "ledger.sqlite"
            upsert_clips(
                db,
                [
                    {
                        **clip("c1", 3600, "luganda"),
                        "license_name": "CC0",
                        "source_id": "s1",
                        "split": "train",
                        "training_allowed": 1,
                    }
                ],
            )
            preflight = root / "preflight.json"
            preflight.write_text(json.dumps({"passed": True, "checks": {"audit_gate": True}}))
            worst = root / "worst.json"
            worst.write_text(
                json.dumps(
                    {
                        "rows": [
                            {
                                "rank": 1,
                                "accent_family": "luganda",
                                "group_metric": 8.5,
                                "train_hours": 0.0,
                                "recommended_action": "acquire_or_license_training_audio",
                            }
                        ]
                    }
                )
            )
            manifest = root / "manifest.csv"
            manifest.write_text(
                "clip_id,source,license,redistributable\n"
                "c1,fixture,CC-BY-NC-SA-4.0,no\n"
            )
            receipt = root / "plan.json"
            result = studio_distillation_plan(
                db,
                metrics={
                    "worst_group_wer": 8.5,
                    "parity_gap": 8.0,
                    "by_accent_family": {"luganda": 8.5, "english": 0.5},
                },
                previous_metrics={"worst_group_wer": 0.9, "parity_gap": 0.6},
                preflight_receipt=preflight,
                worst_cell_plan_receipt=worst,
                manifest_csv=manifest,
                host_profile="mac_studio_m1_ultra_128gb",
                seeds=(7,),
                top_cells=1,
                output_receipt=receipt,
            )
            self.assertTrue(result["launch_authorized_on_this_host"])
            self.assertEqual(result["release_expectation"]["status"], "non_release_expected")
            self.assertEqual(result["group_dro"]["status"], "blocked")
            self.assertIn("licensed training audio missing", " ".join(result["group_dro"]["blockers"]))
            command = result["tiny_train_to_score"]["commands"][0]
            self.assertIn("scripts/local_scout_distill.py", command["train_command"])
            self.assertIn("--device mps", command["train_command"])
            self.assertIn("babel run-cycle", command["run_cycle_command"])
            self.assertEqual(result["input_evidence"]["license_summary"]["redistributable_values"], ["no"])
            self.assertTrue(receipt.exists())

    def test_quality_cards_write_per_group_failure_cards(self):
        with tempfile.TemporaryDirectory() as tmp:
            rows = [
                {
                    "clip_id": "clip-a",
                    "accent_family": "igbo",
                    "reference": "hello world",
                    "hypothesis": "hello",
                    "wer": 0.5,
                }
            ]
            cards = quality_cards(
                rows,
                {
                    "worst_group_wer": 0.5,
                    "parity_gap": 0.0,
                    "by_accent_family": {"igbo": 0.5},
                },
                output_dir=Path(tmp) / "cards",
                model_name="scout",
                release_decision={"passed": False, "failures": ["worst_group_wer regressed"]},
                manifest_rows=[
                    {
                        "clip_id": "clip-a",
                        "source": "fixture",
                        "license": "CC0",
                        "redistributable": "yes",
                        "split": "eval",
                    }
                ],
                receipt_path="receipt.json",
                card_id="scout",
            )
            self.assertEqual(cards[0]["accent_family"], "igbo")
            text = Path(cards[0]["path"]).read_text()
            self.assertIn("`clip-a`", text)
            self.assertIn("CC0", text)
            self.assertIn("eval", text)
            self.assertIn("hello world", text)
            self.assertIn("candidate output", text)
            self.assertIn("worst_group_wer regressed", text)

    def test_repair_quality_cards_surface_faithfulness_failures(self):
        with tempfile.TemporaryDirectory() as tmp:
            receipt = Path(tmp) / "repair_receipt.json"
            result = repair_quality_cards(
                [
                    {
                        "reference_clean": "Meet at the bank.",
                        "hypothesis_clean": "Meet at the riverside bank at noon.",
                        "decision": "answer",
                        "should_clarify": True,
                        "unsupported_claims": ["riverside", "noon"],
                        "accent_family": "british_isles",
                    }
                ],
                output_dir=Path(tmp) / "cards",
                model_name="stage_b_seed",
                release_decision={"passed": False, "failures": ["unsupported claims"]},
                receipt_path="seed_receipt.json",
                output_receipt=receipt,
                card_id="seed",
            )
            self.assertEqual(result["metrics"]["hallucination_rate"], 1.0)
            self.assertEqual(result["cards"][0]["failures"], 1)
            text = Path(result["cards"][0]["path"]).read_text()
            self.assertIn("faithfulness:** fail", text)
            self.assertIn("unsupported_claims:** riverside, noon", text)
            self.assertIn("should_clarify:** True", text)
            self.assertTrue(receipt.exists())

    def test_assign_splits_and_export_shard(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "ledger.sqlite"
            upsert_clips(
                db,
                [
                    {**clip("a", 1, "caribbean"), "speaker_hash": "speaker-1"},
                    {**clip("b", 1, "caribbean"), "speaker_hash": "speaker-1"},
                    {**clip("c", 1, "african"), "speaker_hash": "speaker-2"},
                    {**clip("q", 1, "african"), "split": "quarantine"},
                ],
            )
            counts = assign_splits(db, train=1, dev=0, test=0)
            self.assertEqual(counts["train"], 3)
            train_rows = export_shard(db, split="train", training_allowed=True)
            self.assertEqual([row["clip_id"] for row in train_rows], ["a", "b", "c"])
            self.assertEqual(export_shard(db, split="quarantine")[0]["clip_id"], "q")
            self.assertEqual(stable_bucket("speaker-1"), stable_bucket("speaker-1"))

    def test_repair_hygiene_assigns_stage_b_only_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "ledger.sqlite"
            upsert_clips(
                db,
                [
                    {
                        **clip("syn_a", None, "caribbean"),
                        "source_type": "synthetic",
                        "license_name": "synthetic-derived",
                        "transcript_type": "synthetic",
                        "redistribution_allowed": None,
                        "source_id": None,
                        "split": None,
                        "notes": "repair; broken=helo || clean=hello",
                    }
                ],
            )
            result = repair_hygiene(db)
            self.assertEqual(result["assigned_split"], 1)
            self.assertEqual(result["filled_source_id"], 1)
            self.assertEqual(result["remaining_unassigned"], 0)
            rows = export_shard(db, split="repair_train")
            self.assertEqual(rows[0]["source_id"], "synthetic-repair:syn_a")
            self.assertEqual(rows[0]["redistribution_allowed"], 0)
            self.assertEqual(ledger_issues(db)["unassigned_eligible"], [])

    def test_audit_blocks_license_and_defects(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "ledger.sqlite"
            upsert_clips(
                db,
                [
                    {
                        **clip("bad-license", 1, "caribbean"),
                        "split": "train",
                    },
                    {
                        **clip("bad-audio", 1, "caribbean"),
                        "license_name": "CC0",
                        "split": "train",
                        "noise_tier": "defective",
                    },
                ],
            )
            issues = ledger_issues(db)
            self.assertEqual(len(issues["license"]), 1)
            self.assertEqual(len(issues["defects"]), 1)
            report = audit(db)
            self.assertFalse(report["passed"])
            self.assertIn("license: 1", report["failures"])

    def test_cli_eval_asr(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "eval.jsonl"
            path.write_text(
                json.dumps(
                    {
                        "reference": "book it for four",
                        "hypothesis": "book it for fourteen",
                        "accent_family": "caribbean",
                    }
                )
            )
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(main(["eval-asr", str(path)]), 0)
            self.assertAlmostEqual(json.loads(out.getvalue())["wer"], 0.25)

    def test_cli_validate_dir_and_segmentation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "ok.json").write_text(json.dumps(STAGE_B_CLARIFY))
            (root / "bad.json").write_text(json.dumps({"schema_version": "babel.stage_b.v0"}))
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["validate-dir", str(root)]), 1)  # one file fails
            seg = root / "seg.jsonl"
            seg.write_text(json.dumps({"reference": "Yes. No.", "hypothesis": "yes no", "accent_family": "x"}))
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(main(["eval-segmentation", str(seg)]), 0)
            self.assertEqual(json.loads(out.getvalue())["boundary_f1"], 0.0)


if __name__ == "__main__":
    unittest.main()
