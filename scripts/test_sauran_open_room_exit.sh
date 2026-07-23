#!/usr/bin/env bash
# Regression: room 13 in the fixed Sauran world is intentionally unsealed.
# The pilot must take its forward door instead of treating a split Rift Ooze
# as a mandatory clear and idling in optional combat for the whole run.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ROM="${1:-$ROOT/rom/working/quintra.gbc}"
OUT="$ROOT/tmp/sauran-open-room-exit.csv"

# This is an optional-combat routing fixture, not a Normal boss-balance gate.
# Use the coarse tester assist so the baseline giant experiment cannot end the
# run at boss one before room 13 exists.
QUINTRA_BOT_EASY=1 QUINTRA_BOT_GIANT_POLICY=baseline \
  QUINTRA_FIXED_MATRIX_CLASSES=1 \
  QUINTRA_FIXED_MATRIX_FRAMES=30000 \
  QUINTRA_FIXED_MATRIX_OUT="$OUT" \
  QUINTRA_FIXED_MATRIX_SAVE_DIR="$ROOT/tmp/sauran-open-room-exit-saves" \
  bash "$ROOT/scripts/fixed_controller_matrix.sh" "$ROM" >/dev/null

awk -F, '
  NR == 1 { for (i = 1; i <= NF; ++i) col[$i] = i; next }
  {
    rows++
    if ($(col["seed"]) != 2064128647) wrong_seed = 1
    if ($(col["max_room"]) < 14) no_exit = 1
    if ($(col["max_target_stall_room"]) == 13 && $(col["max_target_stall_frames"]) > 720) ooze_stall = 1
  }
  END {
    if (rows != 1) { print "[sauran-open-room] missing fixed controller row" > "/dev/stderr"; exit 1 }
    if (wrong_seed) { print "[sauran-open-room] fixed controller world drifted" > "/dev/stderr"; exit 1 }
    if (no_exit) { print "[sauran-open-room] did not leave open room 13" > "/dev/stderr"; exit 1 }
    if (ooze_stall) { print "[sauran-open-room] optional Rift Ooze still stalled room 13" > "/dev/stderr"; exit 1 }
  }
' "$OUT"
echo "[sauran-open-room] PASS optional Rift Ooze yields to the open forward exit"
