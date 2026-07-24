#!/usr/bin/env bash
# Regression: Vespine's Stinger route used to let a wall-adjacent Rope drain
# the entire run. The controller must spend its real double-tap dash after the
# observed body hit and leave a Rope encounter rather than merely avoiding a
# combat-stall classification. The former run-32 room-7 sample now dies before
# the first boss because the expanded maze correctly removed its row
# shortcuts; use the paired long-wing sample that demonstrably encounters a
# Rope and continues beyond a boss. Easy preserves the Rope's movement and
# body-pin geometry while keeping the longer setup route from ending on
# unrelated attrition.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ROM="${1:-$ROOT/rom/working/quintra.gbc}"
OUT="$(mktemp /tmp/quintra-vespine-rope.XXXXXX)"

QUINTRA_BOT_EASY=1 QUINTRA_BALANCE_RUNS=2 QUINTRA_BALANCE_CLASSES=4 \
  QUINTRA_BALANCE_TARGET_FRAME=540 \
  QUINTRA_BALANCE_FRAMES=18000 QUINTRA_BALANCE_HOST_TIMEOUT=180 \
  QUINTRA_BALANCE_OUT="$OUT" \
  bash "$ROOT/scripts/run_balance_bot.sh" "$ROM" >/dev/null

awk -F, '
  NR == 1 {
    for (i = 1; i <= NF; ++i) col[$i] = i
    next
  }
  NR == 2 {
    if ($(col["seed"]) != 2064128343) {
      print "[vespine-rope] fixed controller world drifted" > "/dev/stderr"
      exit 1
    }
    if ($(col["max_room"]) < 13 || and($(col["enemy_mask"]), 512) == 0) {
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
