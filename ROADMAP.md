# Roadmap

Babel today is an evaluation harness and a worst-group-WER benchmark. The work
ahead is to train the model the benchmark is built to judge. The heavy training
runs on an Apple M2 Max Mac Studio (96 GB), which brings every stage in-house.

## Now (works today)
- The experiment ledger, the from-scratch WER / CER and worst-group-parity
  metrics, the release gates, and the worst-group benchmark.
- A Whisper distillation harness that runs without collapsing (KL + CE,
  decoder pruning, collapse guard).
- Reference baselines for the teacher and the un-distilled tiny floor.

## Next
- Acoustic distillation to convergence on the Mac Studio: a flagship tier and a
  smaller sheared tier, judged only by worst-group WER.
- Group-DRO parity training to directly minimize the worst-group error.

## Later
- A second-stage repair / generative-error-correction model over the N-best
  output, to fix intent without rewriting faithful transcriptions.
- Quantization-aware distillation and a small on-device Rust runtime, so the
  finished model can ship as a tiny local artifact.
