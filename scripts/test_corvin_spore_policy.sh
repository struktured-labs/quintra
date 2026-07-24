#!/usr/bin/env bash
# Regression: Toxic Mire spikes are hazardous feet terrain, not projectile
# cover. On deterministic Corvin seed two, treating them as shot-blocking made
# the controller orbit a reachable Mire Spore in room 26 for more than a
# minute. The real ranged lane must clear that room and reach the fifth boss
# threshold without a live-combat stall.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ROM="${1:-$ROOT/rom/working/quintra.gbc}"
OUT="$(mktemp /tmp/quintra-corvin-spore.XXXXXX)"

# Deep mine-lane geometry check: Easy keeps the same procedural room, Spore,
# and ranged collision rules while ensuring harder preceding colossi do not
# prevent the controller from reaching the actual fixture.
QUINTRA_BOT_EASY=1 QUINTRA_BALANCE_RUNS=2 QUINTRA_BALANCE_CLASSES=2 \
  QUINTRA_BALANCE_FRAMES=30000 QUINTRA_BALANCE_HOST_TIMEOUT=240 \
  QUINTRA_BALANCE_OUT="$OUT" \
  bash "$ROOT/scripts/run_balance_bot.sh" "$ROM" >/dev/null

awk -F, '
  NR == 1 {
    for (i = 1; i <= NF; ++i) col[$i] = i
    next
  }
  {
    rows++
    if ($(col["max_room"]) < 30) weak = 1
    if ($(col["max_target_stall_room"]) == 26 &&
        $(col["max_target_stall_frames"]) > 3600 && $(col["min_hp"]) > 0) stalled = 1
  }
  END {
    if (rows != 1) { print "[corvin-spore] missing deterministic row" > "/dev/stderr"; exit 1 }
    if (weak) { print "[corvin-spore] did not clear the Mire Spore threshold" > "/dev/stderr"; exit 1 }
    if (stalled) { print "[corvin-spore] live Mire Spore combat stall" > "/dev/stderr"; exit 1 }
  }
' "$OUT"
echo "[corvin-spore] PASS Corvin clears the Toxic Mire mine lane without a stall"
