#!/usr/bin/env bash
# Regression: Sauran's Tail Spike classwise giant policy must preserve a safe,
# productive pressure lane. The fresh-SRAM paired sample must clear every first
# boss and at least four giants without a player death. `max_combat_frames` is
# intentionally not used here: it measures whole procedural-room age, not a
# no-progress interval, and can include several legitimate sequential fights.
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
    if ($(col["bosses"]) >= 1) first_bosses++
    if ($(col["death_source"]) != 255) died = 1
  }
  END {
    if (rows != 3) { print "[sauran-boss] missing paired rows" > "/dev/stderr"; exit 1 }
    if (first_bosses != 3) { print "[sauran-boss] classwise policy missed a first boss" > "/dev/stderr"; exit 1 }
    if (bosses < 4) { print "[sauran-boss] classwise policy cleared fewer than four giants" > "/dev/stderr"; exit 1 }
    if (died) { print "[sauran-boss] classwise policy caused a player death" > "/dev/stderr"; exit 1 }
  }
' "$OUT"
echo "[sauran-boss] PASS paired policy cleared every first boss and four giants without a death"
