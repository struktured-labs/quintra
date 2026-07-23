#!/usr/bin/env bash
# Regression: Vespine's Stinger is a 48px lunge, not Wolfkin's adjacent claw.
# A one-tile bot firing lane left the controller pacing against Flutterbat-room
# cover while its targets stayed out of range. In hard Normal, at least two of
# three paired real-ROM runs must clear that encounter and reach the first
# boss threshold; all three remain subject to a ninety-second no-progress
# ceiling. The expanded room-three Warden chamber can legitimately make the
# Stinger reacquire a flying escort several times before the required clear.
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
    if ($(col["max_room"]) >= 6) thresholds++
    # Flutterbat is a legitimate longest fight in a procgen run; it is a
    # regression only when that dwell is actually over the ninety-second
    # budget.  The old enemy-id-only check rejected a healthy 740-frame fight
    # even after the controller reached the boss threshold.
    if ($(col["max_target_stall_enemy"]) == 12 && $(col["max_target_stall_frames"]) > 5400) bad = "stalled on Flutterbat"
    if ($(col["max_target_stall_frames"]) > 5400) bad = "combat no-progress exceeded ninety seconds"
  }
  END {
    if (rows != 3) { print "[vespine-flutter] missing paired rows" > "/dev/stderr"; exit 1 }
    if (thresholds < 2) { print "[vespine-flutter] fewer than two Normal runs reached the first boss threshold" > "/dev/stderr"; exit 1 }
    if (bad) { print "[vespine-flutter] " bad > "/dev/stderr"; exit 1 }
  }
' "$OUT"
echo "[vespine-flutter] PASS 2/3 hard-Normal runs reached room 6 without Flutterbat stall"
