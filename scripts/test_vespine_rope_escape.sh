#!/usr/bin/env bash
# Regression: Vespine's short Stinger route used to let a wall-adjacent Rope
# drain the entire run in room 7. The controller must spend its real
# double-tap dash after the observed body hit, clear the next boss, and leave
# that encounter rather than merely avoiding a combat-stall classification.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ROM="${1:-$ROOT/rom/working/quintra.gbc}"
OUT="$(mktemp /tmp/quintra-vespine-rope.XXXXXX)"

QUINTRA_BALANCE_RUNS=3 QUINTRA_BALANCE_CLASSES=4 \
  QUINTRA_BALANCE_FRAMES=16000 QUINTRA_BALANCE_HOST_TIMEOUT=45 \
  QUINTRA_BALANCE_OUT="$OUT" \
  bash "$ROOT/scripts/run_balance_bot.sh" "$ROM" >/dev/null

awk -F, '
  NR == 1 {
    for (i = 1; i <= NF; ++i) col[$i] = i
    next
  }
  NR == 2 {
    if ($(col["max_room"]) < 13) {
      print "[vespine-rope] did not escape the deterministic Rope lane" > "/dev/stderr"
      exit 1
    }
    if ($(col["bosses"]) < 2) {
      print "[vespine-rope] did not clear the second boss after Rope contact" > "/dev/stderr"
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
