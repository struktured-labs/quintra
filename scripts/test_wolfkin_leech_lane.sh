#!/usr/bin/env bash
# Regression: a clear 45px Gloom Leech lane is inside Wolfkin's authored
# 64px Fang-Stab reach. The pilot must attack it rather than spend an entire
# sealed room re-routing beneath the wall.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ROM="${1:-$ROOT/rom/working/quintra.gbc}"
OUT="$(mktemp /tmp/quintra-wolfkin-leech-lane.XXXXXX)"

# This pins Wolfkin's lane selection, while the direct live-ROM test owns the
# attach/dash/re-attach timing contract. Use the coarse tester assist so a
# route assertion does not become a second Normal combat-balance gate.
QUINTRA_BOT_EASY=1 QUINTRA_BALANCE_RUNS=2 QUINTRA_BALANCE_CLASSES=0 \
  QUINTRA_BALANCE_FRAMES=5000 QUINTRA_BALANCE_HOST_TIMEOUT=40 \
  QUINTRA_BALANCE_OUT="$OUT" QUINTRA_BALANCE_SKIP_REPORT=1 \
  bash "$ROOT/scripts/run_balance_bot.sh" "$ROM" >/dev/null

awk -F, '
  NR == 1 {
    for (i = 1; i <= NF; ++i) col[$i] = i
    next
  }
  {
    rows++
    if ($(col["seed"]) != 2064128565) wrong_seed = 1
    if ($(col["max_room"]) < 3) missed_required = 1
    if ($(col["max_target_stall_room"]) == 1 && $(col["max_target_stall_enemy"]) == 13 && $(col["max_target_stall_frames"]) > 360) leech_stall = 1
  }
  END {
    if (rows != 1) { print "[wolfkin-leech-lane] missing fixed row" > "/dev/stderr"; exit 1 }
    if (wrong_seed || missed_required || leech_stall) {
      print "[wolfkin-leech-lane] Fang lane failed to clear the sealed Leech route" > "/dev/stderr"
      exit 1
    }
  }
' "$OUT"
echo "[wolfkin-leech-lane] PASS Wolfkin uses the clear 64px Fang lane"
