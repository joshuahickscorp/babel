# Babel

Babel is a local-first research spine for a forgiving speech engine: a pipeline
that preserves literal accented speech, repairs intent only when it can stay
faithful, and measures quality by worst-group behavior rather than aggregate
accuracy alone.

This repository currently contains the source package, CLI contracts, tests, and
planning documents for the local validation loop. Large generated artifacts such
as corpora, audio shards, model checkpoints, local eval outputs, and cloud
handoff logs are intentionally excluded from git.

## What Is Here

- `src/babel/`: core contracts, ledger helpers, metrics, release gates, and CLI.
- `tests/`: unit coverage for schema validation, ledgers, metrics, and gates.
- `scripts/`: reusable local analysis utilities that are safe to publish.
- `babel.md`: architecture and research plan.
- `PLAN.md`: current implementation plan.

## Quick Check

```bash
PYTHONPATH=src python -m unittest discover -s tests -q
```

## Status

This is an early research/workbench repository. It is not a packaged speech
model and does not include training data or model weights.
