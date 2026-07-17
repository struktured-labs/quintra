#!/usr/bin/env bash
# Regression: Wolfkin's adjacent Claw needs a measured pulse-fire giant lane.
# On paired deterministic seeds, the direct baseline cleared no first boss;
# classwise play must clear at least one without a live-combat stall.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ROM="${1:-$ROOT/rom/working/quintra.gbc}"
OUT="$(mktemp /tmp/quintra-wolfkin-boss.XXXXXX)"

QUINTRA_BALANCE_REPS=3 QUINTRA_BALANCE_CLASSES=0 \
  QUINTRA_BALANCE_FRAMES=18000 QUINTRA_BALANCE_HOST_TIMEOUT=40 \
  QUINTRA_BALANCE_OUT="$OUT" \
  bash "$ROOT/scripts/run_balance_bot.sh" "$ROM" >/dev/null

awk -F, '
  NR == 1 {
    for (i = 1; i <= NF; ++i) col[$i] = i
    next
  }
  {
    rows++
    bosses += $(col["bosses"])
    if ($(col["max_combat_frames"]) > 3600 && $(col["min_hp"]) > 0)
      stalled = 1
  }
  END {
    if (rows != 3) { print "[wolfkin-boss] missing paired rows" > "/dev/stderr"; exit 1 }
    if (bosses < 1) { print "[wolfkin-boss] classwise policy cleared no first boss" > "/dev/stderr"; exit 1 }
    if (stalled) { print "[wolfkin-boss] live-combat stall" > "/dev/stderr"; exit 1 }
  }
' "$OUT"
echo "[wolfkin-boss] PASS paired policy cleared a boss without a stall"
