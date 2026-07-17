#!/usr/bin/env bash
# Regression: Picsean's real Tidal Wave guard must cover the mandatory
# Riftwild lane when a nearby body threat cannot be sidestepped. This
# controller-only seed used to die after its first boss in room 7; it should
# now cross the world, clear a second boss, and reach the next dungeon.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ROM="${1:-$ROOT/rom/working/quintra.gbc}"
OUT="$(mktemp /tmp/quintra-picsean-riftwild.XXXXXX)"

QUINTRA_BALANCE_RUNS=2 QUINTRA_BALANCE_CLASSES=3 \
  QUINTRA_BALANCE_FRAMES=18000 QUINTRA_BALANCE_HOST_TIMEOUT=40 \
  QUINTRA_BALANCE_OUT="$OUT" \
  bash "$ROOT/scripts/run_balance_bot.sh" "$ROM" >/dev/null

awk -F, '
  NR == 1 {
    for (i = 1; i <= NF; ++i) col[$i] = i
    next
  }
  NR == 2 {
    if ($(col["bosses"]) < 2) {
      print "[picsean-riftwild] did not clear the second boss" > "/dev/stderr"
      exit 1
    }
    if ($(col["max_room"]) < 16 || $(col["world_hops"]) < 10) {
      print "[picsean-riftwild] did not cross Riftwild into the next dungeon" > "/dev/stderr"
      exit 1
    }
    if ($(col["max_combat_frames"]) > 3600 && $(col["min_hp"]) > 0) {
      print "[picsean-riftwild] live-combat stall" > "/dev/stderr"
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
