#!/usr/bin/env bash
# Full headless balance sweep: PyBoy boss/room slices for every tier, hero
# and stage, plus a bounded mGBA whole-run sample, then the difficulty report.
# Logs to $OUT/sweep.log and prints a short summary. Not a CI job.
#
#   bash scripts/balance_full_sweep.sh            # defaults below
#   SEEDS=8 JOBS=20 RUN_SEEDS=2 bash scripts/balance_full_sweep.sh
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
OUT="${OUT:-$ROOT/tmp/balance/full}"
SEEDS="${SEEDS:-4}"
RUN_SEEDS="${RUN_SEEDS:-1}"
JOBS="${JOBS:-$(( $(nproc) * 3 / 4 ))}"
DIFFICULTY="${DIFFICULTY:-normal}"
TIERS="${TIERS:-bot skilled average nonexpert}"
ROM="$ROOT/rom/working/quintra.gbc"
PY=(uv run --quiet --with "pyboy==2.7.0" --with pillow python)
export PYTHONPATH="$ROOT/scripts/quintra_sitecustomize"
export QUINTRA_STATE_WAIVE_CHECKS="${QUINTRA_STATE_WAIVE_CHECKS:-marked_gate}"
mkdir -p "$OUT"
LOG="$OUT/sweep.log"
: > "$LOG"
{
  echo "[full] $(date) rom $(sha256sum "$ROM" | cut -c1-12) seeds=$SEEDS jobs=$JOBS"
  STATES="$OUT/stage-states"
  if [ ! -f "$STATES/manifest.json" ] || ! grep -q "$(sha256sum "$ROM" | cut -d' ' -f1)" "$STATES/manifest.json"; then
    rm -rf "$STATES" "$OUT/stage-parts" && mkdir -p "$OUT/stage-parts"
    for s in 1 2 3 4 5 6 7 8 9; do
      for h in wolfkin sauran corvin picsean vespine; do
        "${PY[@]}" scripts/make_stage_states.py --rom "$ROM" --stage "$s" --champion "$h" \
          --difficulty "$DIFFICULTY" --out "$OUT/stage-parts/s$s-$h" \
          > "$OUT/stage-parts/s$s-$h.log" 2>&1 \
          || echo "[full] state generation failed s$s $h: $(tail -1 "$OUT/stage-parts/s$s-$h.log")" &
      done
      wait
    done
    python3 scripts/balance_merge_states.py "$OUT/stage-parts" "$STATES"
  fi
  # shellcheck disable=SC2086
  "${PY[@]}" scripts/balance_arena.py --rom "$ROM" --state-dir "$STATES" \
    --skills $TIERS --stages 1-9 --seeds "$SEEDS" --jobs "$JOBS" \
    --difficulty "$DIFFICULTY" --out "$OUT/arena.csv"
  if [ "$RUN_SEEDS" -gt 0 ] && command -v mgba-headless >/dev/null; then
    # shellcheck disable=SC2086
    python3 scripts/balance_sweep.py --mode full --skills $TIERS --classes 0 1 2 3 4 \
      --seeds "$RUN_SEEDS" --frames 108000 --jobs "$JOBS" --timeout 900 \
      --difficulty "$DIFFICULTY" --out "$OUT/runs" || true
  fi
  RUNS_ARG=()
  [ -f "$OUT/runs/stages.csv" ] && RUNS_ARG=(--runs "$OUT/runs/stages.csv")
  "${PY[@]}" scripts/balance_report.py "$OUT/arena.csv" "${RUNS_ARG[@]}" \
    --out "$OUT/report" --check scripts/balance_thresholds.json
  echo "[full] $(date) done"
} >> "$LOG" 2>&1
grep -E "^\[(full|arena|sweep|report)\]" "$LOG" | tail -12
echo "report: $OUT/report/report.md"
