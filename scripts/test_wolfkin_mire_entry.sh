#!/usr/bin/env bash
# Regression: the melee champion must survive and traverse the Toxic Mire
# entrance without an optional stationary Spore creating a route stall. Start
# from the release gate's native Stage 5 checkpoint so this remains a Mire
# contract after the campaign expanded from compact global room 25 to 87+.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ROM="${1:-$ROOT/rom/working/quintra.gbc}"
OUT="$(mktemp /tmp/quintra-wolfkin-mire-entry.XXXXXX)"
STATE="$ROOT/tmp/mgba-states-smoke/quintra-stage-05-entry-wolfkin-easy.ss0"
test -s "$STATE"

# This is a deep fixture/reachability contract, not a Normal balance proof.
# The state supplies progression only; every step and attack from the true
# Mire entrance onward remains ordinary controller input.
QUINTRA_MGBA_STATE="$STATE" QUINTRA_BALANCE_RESUME_STATE=1 \
  QUINTRA_BOT_EASY=1 QUINTRA_BALANCE_RUNS=4 QUINTRA_BALANCE_CLASSES=0 \
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
    if ($(col["max_room"]) < 90 || $(col["rooms_seen"]) < 8) stranded = 1
    # Road Echoes are now hidden optional discoveries, so this fixed solo path
    # reaches eight Mire rooms without necessarily visiting the optional cell
    # that rolls a Spore. Live Spore identity/arming remains mandatory in the
    # dedicated enemy contract; if one appears here, retain the stall check.
    # The CSV retains the single longest target stall across the whole run.
    # Only classify it as this fixture when it belongs to the room-25 Mire
    # Spore itself; a longer, unrelated encounter elsewhere must not turn a
    # successful room-25 crossing into a false Spore regression.
    if ($(col["max_target_stall_frames"]) > 7200 &&
        $(col["max_target_stall_room"]) >= 87 &&
        $(col["max_target_stall_room"]) <= 110 &&
        $(col["max_target_stall_enemy"]) == 17) stalled = 1
  }
  END {
    if (rows != 1) { print "[wolfkin-mire-entry] missing fixed controller row" > "/dev/stderr"; exit 1 }
    if (stranded) { print "[wolfkin-mire-entry] Toxic Mire entry was not survivable" > "/dev/stderr"; exit 1 }
    if (stalled) { print "[wolfkin-mire-entry] live Mire Spore combat stall" > "/dev/stderr"; exit 1 }
  }
' "$OUT"
echo "[wolfkin-mire-entry] PASS Wolfkin crosses the Toxic Mire entry without a stall"
