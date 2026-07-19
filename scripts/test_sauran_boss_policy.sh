#!/usr/bin/env bash
# Regression: Sauran's Tail Spike must route around cover instead of stalling
# on a wall-clinging Gloom Leech. The fresh-SRAM classwise sample must retain
# a first-boss clear without either a live-combat or route stall.
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
    if ($(col["max_route_frames"]) > 3600 && $(col["min_hp"]) > 0)
      route_stalled = 1
  }
  END {
    if (rows != 3) { print "[sauran-boss] missing paired rows" > "/dev/stderr"; exit 1 }
    if (bosses < 1) { print "[sauran-boss] classwise policy cleared no first boss" > "/dev/stderr"; exit 1 }
    if (stalled) { print "[sauran-boss] live-combat stall" > "/dev/stderr"; exit 1 }
    if (route_stalled) { print "[sauran-boss] live-route stall" > "/dev/stderr"; exit 1 }
  }
' "$OUT"
echo "[sauran-boss] PASS paired policy cleared a boss without a stall"
