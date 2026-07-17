#!/usr/bin/env bash
# Regression: Vespine's close Stinger benefits from the measured pulse-fire
# giant lane. Paired baseline cleared one first boss; classwise play must
# retain at least two without a live-combat stall.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ROM="${1:-$ROOT/rom/working/quintra.gbc}"
OUT="$(mktemp /tmp/quintra-vespine-boss.XXXXXX)"

QUINTRA_BALANCE_REPS=3 QUINTRA_BALANCE_CLASSES=4 \
  QUINTRA_BALANCE_FRAMES=18000 QUINTRA_BALANCE_HOST_TIMEOUT=45 \
  QUINTRA_MGBA_SAVE_DIR="${OUT}.save" QUINTRA_BALANCE_OUT="$OUT" \
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
    if (rows != 3) { print "[vespine-boss] missing paired rows" > "/dev/stderr"; exit 1 }
    if (bosses < 2) { print "[vespine-boss] classwise policy cleared fewer than two bosses" > "/dev/stderr"; exit 1 }
    if (stalled) { print "[vespine-boss] live-combat stall" > "/dev/stderr"; exit 1 }
  }
' "$OUT"
echo "[vespine-boss] PASS paired policy cleared two bosses without a stall"
