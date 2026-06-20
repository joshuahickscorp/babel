import contextlib
import io
import json
import math
import struct
import tempfile
import unittest
import wave
from pathlib import Path

from babel import (
    assign_splits,
    audit,
    boundary_f1,
    cer,
    coverage,
    coverage_entropy,
    coverage_gaps,
    eval_asr,
    eval_nbest,
    eval_repair,
    eval_segmentation,
    export_shard,
    experiments,
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
    record_experiment,
    release_gate,
    review_queue,
    route_stage_a,
    scorecard,
    split_leaks,
    stable_bucket,
    upsert_clip,
    upsert_clips,
    validate_dir,
    validate_stage,
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
