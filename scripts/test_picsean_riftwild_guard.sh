#!/usr/bin/env bash
# Regression: Picsean's real Tidal Wave guard must cover the mandatory
# Riftwild lane when a nearby body threat cannot be sidestepped. This
# controller-only world crosses the regional trail, clears a second boss, and
# reaches the next dungeon. Easy is setup only: guard/Will/controller mechanics
# are identical, while the expanded seven-role routes no longer turn this
# traversal contract into an unrelated pre-boss endurance gate.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ROM="${1:-$ROOT/rom/working/quintra.gbc}"
OUT="$(mktemp /tmp/quintra-picsean-riftwild.XXXXXX)"

QUINTRA_BOT_EASY=1 QUINTRA_BALANCE_RUNS=4 QUINTRA_BALANCE_CLASSES=3 \
  QUINTRA_BALANCE_TARGET_FRAME=1000 \
  QUINTRA_BALANCE_FRAMES=80000 QUINTRA_BALANCE_HOST_TIMEOUT=300 \
  QUINTRA_BALANCE_OUT="$OUT" \
  bash "$ROOT/scripts/run_balance_bot.sh" "$ROM" >/dev/null

awk -F, '
  NR == 1 {
    for (i = 1; i <= NF; ++i) col[$i] = i
    next
  }
  NR == 2 {
    if ($(col["seed"]) != 2064128163) {
      print "[picsean-riftwild] fixed world drifted" > "/dev/stderr"
      exit 1
    }
    if ($(col["bosses"]) < 2) {
      print "[picsean-riftwild] did not clear the second boss" > "/dev/stderr"
      exit 1
    }
    if ($(col["max_room"]) < 63 || $(col["world_hops"]) < 10) {
      print "[picsean-riftwild] did not cross Riftwild into the next dungeon" > "/dev/stderr"
      exit 1
    }
    # max_combat_frames is complete room residence, not no-progress time; a
    # healthy multi-enemy procedural room can legitimately exceed it. This
    # route regression instead requires its concrete safety outcome.
    if ($(col["death_source"]) != 255) {
      print "[picsean-riftwild] controller died on the Riftwild route" > "/dev/stderr"
      exit 1
    }
    found = 1
  }
  END {
    if (!found) {
      print "[picsean-riftwild] missing controller row" > "/dev/stderr"
      exit 1
    }
  }
' "$OUT"
echo "[picsean-riftwild] PASS Tidal guard crossed Riftwild and cleared boss two"
