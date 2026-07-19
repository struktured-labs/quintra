#!/usr/bin/env bash
# Regression: a stationary Mire Spore must never arm at the room entrance
# before the melee champion gets a readable first movement choice. This fixed
# controller world used to pin Wolfkin in room 25 for more than a minute;
# it must now cross the Toxic Mire entry and retain a live combat ceiling.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ROM="${1:-$ROOT/rom/working/quintra.gbc}"
OUT="$(mktemp /tmp/quintra-wolfkin-mire-entry.XXXXXX)"

QUINTRA_BALANCE_RUNS=4 QUINTRA_BALANCE_CLASSES=0 \
  QUINTRA_BALANCE_TARGET_FRAME=460 \
  QUINTRA_BALANCE_FRAMES=20000 QUINTRA_BALANCE_HOST_TIMEOUT=40 \
  QUINTRA_BALANCE_OUT="$OUT" \
  bash "$ROOT/scripts/run_balance_bot.sh" "$ROM" >/dev/null

awk -F, '
  NR == 1 {
    for (i = 1; i <= NF; ++i) col[$i] = i
    next
  }
  {
    rows++
    if ($(col["seed"]) != 2064128647) wrong_seed = 1
    if ($(col["max_room"]) < 29) stranded = 1
    if ($(col["min_hp"]) == 0) died = 1
    if ($(col["max_target_stall_frames"]) > 7200) stalled = 1
  }
  END {
    if (rows != 1) { print "[wolfkin-mire-entry] missing fixed controller row" > "/dev/stderr"; exit 1 }
    if (wrong_seed) { print "[wolfkin-mire-entry] controller world drifted" > "/dev/stderr"; exit 1 }
    if (stranded || died) { print "[wolfkin-mire-entry] Toxic Mire entry was not survivable" > "/dev/stderr"; exit 1 }
    if (stalled) { print "[wolfkin-mire-entry] live Mire Spore combat stall" > "/dev/stderr"; exit 1 }
  }
' "$OUT"
echo "[wolfkin-mire-entry] PASS Wolfkin crosses the Toxic Mire entry without a stall"
