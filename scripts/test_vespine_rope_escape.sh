#!/usr/bin/env bash
# Regression: Vespine's short Stinger route used to let a wall-adjacent Rope
# drain the entire run in room 7. The controller must spend its real
# double-tap dash after the observed body hit and leave that encounter rather
# than merely avoiding a combat-stall classification. Harder Normal bosses are
# assessed separately; this fixture should not require a second boss clear.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ROM="${1:-$ROOT/rom/working/quintra.gbc}"
OUT="$(mktemp /tmp/quintra-vespine-rope.XXXXXX)"

QUINTRA_BALANCE_RUNS=32 QUINTRA_BALANCE_CLASSES=4 \
  QUINTRA_BALANCE_TARGET_FRAME=400 \
  QUINTRA_BALANCE_FRAMES=16000 QUINTRA_BALANCE_HOST_TIMEOUT=45 \
  QUINTRA_BALANCE_OUT="$OUT" \
  bash "$ROOT/scripts/run_balance_bot.sh" "$ROM" >/dev/null

awk -F, '
  NR == 1 {
    for (i = 1; i <= NF; ++i) col[$i] = i
    next
  }
  NR == 2 {
    if ($(col["seed"]) != 2064128731) {
      print "[vespine-rope] fixed controller world drifted" > "/dev/stderr"
      exit 1
    }
    if ($(col["max_room"]) < 13) {
      print "[vespine-rope] did not escape the deterministic Rope lane" > "/dev/stderr"
      exit 1
    }
    if ($(col["bosses"]) < 1) {
      print "[vespine-rope] did not reach the post-boss Rope lane" > "/dev/stderr"
      exit 1
    }
    if ($(col["death_source"]) == 9) {
      print "[vespine-rope] Rope still ended the run" > "/dev/stderr"
      exit 1
    }
  }
  END {
    if (NR != 2) {
      print "[vespine-rope] missing deterministic result" > "/dev/stderr"
      exit 1
    }
  }
' "$OUT"
echo "[vespine-rope] PASS body-dash escapes the deterministic Rope pin"
