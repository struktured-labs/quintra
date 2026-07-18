#!/usr/bin/env bash
# Regression: Sauran's 48px Tail Spike benefits from the measured close
# four-beat orbit-fire lane. Its paired seed policy must retain at least four
# boss clears without a live-combat stall.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ROM="${1:-$ROOT/rom/working/quintra.gbc}"
OUT="$(mktemp /tmp/quintra-sauran-boss.XXXXXX)"

QUINTRA_BALANCE_REPS=3 QUINTRA_BALANCE_CLASSES=1 \
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
    if (rows != 3) { print "[sauran-boss] missing paired rows" > "/dev/stderr"; exit 1 }
    if (bosses < 4) { print "[sauran-boss] close orbit policy cleared fewer than four bosses" > "/dev/stderr"; exit 1 }
    if (stalled) { print "[sauran-boss] live-combat stall" > "/dev/stderr"; exit 1 }
  }
' "$OUT"
echo "[sauran-boss] PASS paired policy cleared a boss without a stall"
