# Babel

Babel is a research workbench for accent-robust automatic speech recognition.
It is built around one idea: measure speech models by their worst-group
accuracy on heavily accented, dialectal, and code-switched English, not by an
aggregate number that hides where they fail.

It is a pipeline and a benchmark, not a shipped speech model. No trained model
or weights are included, and the only measured numbers here are reference
baselines (below).

## What is here

- `src/babel/`: the core library, a SQLite experiment ledger, from-scratch
  WER / CER and worst-group-parity metrics, release gates, and the CLI.
- `scripts/distill.py`: a Whisper knowledge-distillation harness (KL + CE loss,
  decoder-layer pruning, and a token-diversity collapse guard).
- `benchmark/`: the worst-group-WER benchmark, with governance, a data
  blocklist, per-accent quality cards, and a "where Babel loses" page.
- `tests/`: unit coverage for the schema, ledger, metrics, and gates.
- `babel.md`: the design and research plan.

Large artifacts (audio corpora, shards, checkpoints, eval outputs) are kept out
of git by design.

## Baselines

Measured on a 353-clip held-out set of accented English, scored by worst-group
WER (lower is better):

- `whisper-large-v3-turbo` (teacher): about 0.22 average WER, about 0.88
  worst-group WER.
- `whisper-tiny` (un-distilled floor): about 0.47 average, about 0.96
  worst-group.

These are the honest starting point. A distilled student that beats the tiny
floor on worst-group WER does not exist yet; the current runs produce a
non-converged smoke checkpoint, not a usable model. See ROADMAP.md.

## Run the tests

```bash
PYTHONPATH=src python -m unittest discover -s tests -q
```

## Status

Early research workbench. No packaged model, no training data, no weights. The
value here is the evaluation harness and the worst-group benchmark, which make
it easy to see exactly where accent-robust ASR breaks.
