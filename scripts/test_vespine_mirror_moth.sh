#!/usr/bin/env bash
# Regression: Frost Vault's Mirror Moth moves opposite player input and fires
# slow reflected bolts. Vespine's ordinary projectile dodge used to abandon
# the Stinger pursuit forever in room 20. The controller must hold the
# body-valid chase, clear that room, and reach the sixth-boss threshold
# without reclassifying a live combat stall as survival.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ROM="${1:-$ROOT/rom/working/quintra.gbc}"
OUT="$(mktemp /tmp/quintra-vespine-mirror.XXXXXX)"

QUINTRA_BALANCE_RUNS=3 QUINTRA_BALANCE_CLASSES=4 \
  QUINTRA_BALANCE_FRAMES=30000 QUINTRA_BALANCE_HOST_TIMEOUT=45 \
  QUINTRA_BALANCE_OUT="$OUT" \
  bash "$ROOT/scripts/run_balance_bot.sh" "$ROM" >/dev/null

awk -F, '
  NR == 1 {
    for (i = 1; i <= NF; ++i) col[$i] = i
    next
  }
  NR == 2 {
    if ($(col["max_room"]) < 42 || $(col["bosses"]) < 6) {
      print "[vespine-mirror] did not clear the Mirror Moth route" > "/dev/stderr"
      exit 1
    }
    if ($(col["max_combat_frames"]) > 3600 && $(col["min_hp"]) > 0) {
      print "[vespine-mirror] live Mirror Moth combat stall" > "/dev/stderr"
      exit 1
    }
    found = 1
  }
  END {
    if (!found) {
      print "[vespine-mirror] missing deterministic row" > "/dev/stderr"
      exit 1
    }
  }
' "$OUT"
echo "[vespine-mirror] PASS Vespine pursues through Mirror Moth bolts"
