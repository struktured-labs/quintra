#!/usr/bin/env bash
# Regression: Toxic Mire spikes are hazardous feet terrain, not projectile
# cover. Start from the release gate's native Stage 5 checkpoint; the real
# ranged lane must cross multiple modern Mire rooms and exercise a live Spore
# without a combat stall.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ROM="${1:-$ROOT/rom/working/quintra.gbc}"
OUT="$(mktemp /tmp/quintra-corvin-spore.XXXXXX)"
STATE="$ROOT/tmp/mgba-states-smoke/quintra-stage-05-entry-corvin-easy.ss0"
test -s "$STATE"

# Deep mine-lane geometry check: Easy keeps the same procedural room, Spore,
# and ranged collision rules while ensuring harder preceding colossi do not
# prevent the controller from reaching the actual fixture.
QUINTRA_MGBA_STATE="$STATE" QUINTRA_BALANCE_RESUME_STATE=1 \
  QUINTRA_BOT_EASY=1 QUINTRA_BALANCE_RUNS=2 QUINTRA_BALANCE_CLASSES=2 \
  QUINTRA_BALANCE_FRAMES=12000 QUINTRA_BALANCE_HOST_TIMEOUT=600 \
  QUINTRA_BALANCE_OUT="$OUT" \
  bash "$ROOT/scripts/run_balance_bot.sh" "$ROM" >/dev/null

awk -F, '
  NR == 1 {
    for (i = 1; i <= NF; ++i) col[$i] = i
    next
  }
  {
    rows++
    if ($(col["max_room"]) < 90 || $(col["rooms_seen"]) < 8) weak = 1
    if (int($(col["enemy_mask"]) / 131072) % 2 == 0) missed_spore = 1
    if ($(col["max_target_stall_room"]) >= 87 &&
        $(col["max_target_stall_room"]) <= 110 &&
        $(col["max_target_stall_enemy"]) == 17 &&
        $(col["max_target_stall_frames"]) > 3600 && $(col["min_hp"]) > 0) stalled = 1
  }
  END {
    if (rows != 1) { print "[corvin-spore] missing deterministic row" > "/dev/stderr"; exit 1 }
    if (weak) { print "[corvin-spore] did not clear the Mire Spore threshold" > "/dev/stderr"; exit 1 }
    if (missed_spore) { print "[corvin-spore] Mire Spore was not exercised" > "/dev/stderr"; exit 1 }
    if (stalled) { print "[corvin-spore] live Mire Spore combat stall" > "/dev/stderr"; exit 1 }
  }
' "$OUT"
echo "[corvin-spore] PASS Corvin clears the Toxic Mire mine lane without a stall"
