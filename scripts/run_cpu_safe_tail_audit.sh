#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SESSION="${SESSION:-babel_cpu_safe_audit}"
LOG="${LOG:-logs/cpu_safe_tail_audit.log}"
OUT="${OUT:-local_tail/audit}"
WORKERS="${WORKERS:-12}"

cd "$ROOT"
mkdir -p logs local_tail

if ! command -v screen >/dev/null 2>&1; then
  echo "screen is required for this detached runner."
  exit 1
fi

if pgrep -fl "scripts/local_scout_distill.py|WhisperForConditionalGeneration|run_cpu_scout" >/dev/null 2>&1; then
  echo "Refusing to start: model/training process appears active."
  pgrep -fl "scripts/local_scout_distill.py|WhisperForConditionalGeneration|run_cpu_scout" || true
  exit 2
fi

if screen -ls | grep -q "[.]${SESSION}[[:space:]]"; then
  echo "screen session already exists: ${SESSION}"
  echo "Use: screen -r ${SESSION}"
  exit 2
fi

screen -dmS "$SESSION" env \
  ROOT="$ROOT" \
  LOG="$LOG" \
  OUT="$OUT" \
  WORKERS="$WORKERS" \
  bash -lc '
set -euo pipefail
cd "$ROOT"
export PYTHONUNBUFFERED=1
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export VECLIB_MAXIMUM_THREADS=1
export NUMEXPR_NUM_THREADS=1

{
  echo "[runner] started: $(date)"
  echo "[runner] CPU-safe: no torch/model imports; workers=$WORKERS"
  echo "[runner] out=$OUT"
  echo
  .venv/bin/python -m py_compile scripts/cpu_safe_tail_audit.py
  .venv/bin/python scripts/cpu_safe_tail_audit.py \
    --workers "$WORKERS" \
    --out "$OUT"
  echo
  echo "[runner] finished: $(date)"
} > "$LOG" 2>&1
'

echo "Started detached CPU-safe audit in screen session: ${SESSION}"
echo "Log: ${LOG}"
echo "Attach: screen -r ${SESSION}"
echo "Detach after attaching: Ctrl-A then D"
