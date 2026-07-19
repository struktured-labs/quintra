#!/usr/bin/env bash
# Deterministic all-champion controller baseline. The bot reaches a public
# title/class-select loop frame using only idle and button input, so every
# selected champion enters the same frame-derived procedural world. This is a
# diagnostic matrix, not a delivery gate: it reports the honest current
# outcomes for a candidate balance change without conflating them with entropy.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ROM="${1:-$ROOT/rom/working/quintra.gbc}"
FRAME="${QUINTRA_FIXED_MATRIX_FRAME:-460}"
EXPECTED_SEED="${QUINTRA_FIXED_MATRIX_SEED:-2064128647}"
RUN="${QUINTRA_FIXED_MATRIX_RUN:-4}"
CLASSES="${QUINTRA_FIXED_MATRIX_CLASSES:-0 1 2 3 4}"
FRAMES="${QUINTRA_FIXED_MATRIX_FRAMES:-90000}"
OUT="${QUINTRA_FIXED_MATRIX_OUT:-$ROOT/tmp/fixed-controller-matrix.csv}"
SAVE="${QUINTRA_FIXED_MATRIX_SAVE_DIR:-$(mktemp -d /tmp/quintra-fixed-matrix.XXXXXX)}"

QUINTRA_BALANCE_RUNS="$RUN" QUINTRA_BALANCE_CLASSES="$CLASSES" \
  QUINTRA_BALANCE_TARGET_FRAME="$FRAME" QUINTRA_BALANCE_FRAMES="$FRAMES" \
  QUINTRA_BALANCE_HOST_TIMEOUT="${QUINTRA_FIXED_MATRIX_HOST_TIMEOUT:-180}" \
  QUINTRA_BALANCE_OUT="$OUT" QUINTRA_MGBA_SAVE_DIR="$SAVE" \
  QUINTRA_BALANCE_SKIP_REPORT=1 \
  bash "$ROOT/scripts/run_balance_bot.sh" "$ROM"

awk -F, -v expected_seed="$EXPECTED_SEED" '
  NR == 1 { for (i = 1; i <= NF; ++i) col[$i] = i; next }
  {
    rows++
    if ($(col["seed"]) != expected_seed) {
      print "[fixed-matrix] unexpected seed " $(col["seed"]) \
        " (expected " expected_seed ")" > "/dev/stderr"
      bad = 1
    }
    printf "[fixed-matrix] class=%s win=%s bosses=%s frames=%s min_hp=%s " \
      "death=%s combat=%s@room%s/enemy%s\n", \
      $(col["class"]), $(col["victory"]), $(col["bosses"]), \
      $(col["frames"]), $(col["min_hp"]), $(col["death_source"]), \
      $(col["max_combat_frames"]), $(col["max_combat_room"]), \
      $(col["max_combat_enemy"])
  }
  END { if (rows == 0 || bad) exit 1 }
' "$OUT"
