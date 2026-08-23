#!/usr/bin/env bash
# Regression: Vespine's close Stinger benefits from the measured pulse-fire
# giant lane. Use the release gate's native boss checkpoint so expanded route
# attrition cannot replace the Stinger/Colossus contract being measured.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ROM="${1:-$ROOT/rom/working/quintra.gbc}"
OUT="$(mktemp /tmp/quintra-vespine-boss.XXXXXX)"
STATE="$ROOT/tmp/mgba-states-smoke/quintra-stage-01-boss-vespine-easy.ss0"
test -s "$STATE"

QUINTRA_MGBA_STATE="$STATE" QUINTRA_BALANCE_RESUME_STATE=1 \
  QUINTRA_BOT_EASY=1 QUINTRA_BALANCE_RUNS=1 QUINTRA_BALANCE_CLASSES=4 \
  QUINTRA_BALANCE_FRAMES=10000 QUINTRA_BALANCE_HOST_TIMEOUT=600 \
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
    attempts += $(col["boss_attempts"])
  }
  END {
    if (rows != 1) { print "[vespine-boss] missing boss row" > "/dev/stderr"; exit 1 }
    if (attempts < 1 || bosses < 1) { print "[vespine-boss] Stinger did not clear the opening giant" > "/dev/stderr"; exit 1 }
  }
' "$OUT"
echo "[vespine-boss] PASS Stinger policy cleared the live opening giant"
