#!/usr/bin/env bash
# Regression: the first Gloam Leech in this fixed Wolfkin route catches the
# champion on the north room edge.  The controller must preserve the real
# double-tap dash rather than replacing it with a generic inward nudge.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ROM="${1:-$ROOT/rom/working/quintra.gbc}"
OUT="$(mktemp /tmp/quintra-wolfkin-leech-edge.XXXXXX)"

QUINTRA_BALANCE_RUNS=1 QUINTRA_BALANCE_CLASSES=0 \
  QUINTRA_BALANCE_TARGET_FRAME=346 \
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
    if ($(col["seed"]) != 2064128529) wrong_seed = 1
    if ($(col["max_room"]) < 18) escaped = 0
    else escaped = 1
    if ($(col["death_source"]) == 13) leech_death = 1
  }
  END {
    if (rows != 1) { print "[wolfkin-leech-edge] missing fixed controller row" > "/dev/stderr"; exit 1 }
    if (wrong_seed) { print "[wolfkin-leech-edge] controller world drifted" > "/dev/stderr"; exit 1 }
    if (!escaped) { print "[wolfkin-leech-edge] Wolfkin did not escape the north-edge Leech room" > "/dev/stderr"; exit 1 }
    if (leech_death) { print "[wolfkin-leech-edge] edge Leech still ended the run" > "/dev/stderr"; exit 1 }
  }
' "$OUT"
echo "[wolfkin-leech-edge] PASS real dash escapes the north-edge Leech latch"
