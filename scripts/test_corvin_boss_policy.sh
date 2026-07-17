#!/usr/bin/env bash
# Regression: Featherbarb's real range supports orbit-and-fire against giants.
# The paired three-seed sweep must retain multiple boss clears without a
# controller-only combat stall.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ROM="${1:-$ROOT/rom/working/quintra.gbc}"
OUT="$(mktemp /tmp/quintra-corvin-boss.XXXXXX)"

QUINTRA_BALANCE_REPS=3 QUINTRA_BALANCE_CLASSES=2 \
  QUINTRA_BALANCE_FRAMES=18000 QUINTRA_BALANCE_HOST_TIMEOUT=45 \
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
    if (rows != 3) { print "[corvin-boss] missing paired rows" > "/dev/stderr"; exit 1 }
    if (bosses < 2) { print "[corvin-boss] orbit policy cleared fewer than two bosses" > "/dev/stderr"; exit 1 }
    if (stalled) { print "[corvin-boss] live-combat stall" > "/dev/stderr"; exit 1 }
  }
' "$OUT"
echo "[corvin-boss] PASS paired orbit policy cleared two bosses without a stall"
