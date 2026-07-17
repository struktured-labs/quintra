#!/usr/bin/env bash
# Regression: Vespine's Stinger is a 48px lunge, not Wolfkin's adjacent claw.
# A one-tile bot firing lane left the controller pacing against Flutterbat-room
# cover while its targets stayed out of range. These three paired real-ROM
# runs must clear that encounter and reach the first boss threshold.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ROM="${1:-$ROOT/rom/working/quintra.gbc}"
OUT="$(mktemp /tmp/quintra-vespine-flutter.XXXXXX)"

QUINTRA_BALANCE_REPS=3 QUINTRA_BALANCE_CLASSES=4 \
  QUINTRA_BALANCE_FRAMES=10800 QUINTRA_BALANCE_HOST_TIMEOUT=40 \
  QUINTRA_BALANCE_OUT="$OUT" \
  bash "$ROOT/scripts/run_balance_bot.sh" "$ROM" >/dev/null

awk -F, '
  NR == 1 {
    for (i = 1; i <= NF; ++i) col[$i] = i
    next
  }
  {
    rows++
    if ($(col["max_room"]) < 6) bad = "did not reach first boss threshold"
    if ($(col["max_combat_enemy"]) == 12) bad = "stalled on Flutterbat"
    if ($(col["max_combat_frames"]) > 3600) bad = "combat dwell exceeded one minute"
  }
  END {
    if (rows != 3) { print "[vespine-flutter] missing paired rows" > "/dev/stderr"; exit 1 }
    if (bad) { print "[vespine-flutter] " bad > "/dev/stderr"; exit 1 }
  }
' "$OUT"
echo "[vespine-flutter] PASS 3 paired runs reached room 6 without Flutterbat stall"
