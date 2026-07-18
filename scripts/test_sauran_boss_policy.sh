#!/usr/bin/env bash
# Regression: Sauran's 48px Tail Spike benefits from the measured orbit-fire
# giant policy. On the paired seeds baseline reached zero first-boss clears;
# classwise policy must retain at least one without a live-combat stall.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ROM="${1:-$ROOT/rom/working/quintra.gbc}"
OUT="$(mktemp /tmp/quintra-sauran-boss.XXXXXX)"
NEAR="$(mktemp /tmp/quintra-sauran-near.XXXXXX)"
FAR="$(mktemp /tmp/quintra-sauran-far.XXXXXX)"

# The offline-search knobs must override the class default. A regression here
# silently turned every range/cadence sweep into the same Sauran policy, so
# differing controller outcomes are the live-ROM contract—not source text.
QUINTRA_BOT_GIANT_POLICY=orbit_fire \
  QUINTRA_BOT_GIANT_RETREAT_RANGE=24 QUINTRA_BOT_GIANT_FIRE_CADENCE=4 \
  QUINTRA_BALANCE_REPS=1 QUINTRA_BALANCE_RUNS=1 QUINTRA_BALANCE_CLASSES=1 \
  QUINTRA_BALANCE_FRAMES=18000 QUINTRA_BALANCE_HOST_TIMEOUT=40 \
  QUINTRA_BALANCE_OUT="$NEAR" \
  bash "$ROOT/scripts/run_balance_bot.sh" "$ROM" >/dev/null

QUINTRA_BOT_GIANT_POLICY=orbit_fire \
  QUINTRA_BOT_GIANT_RETREAT_RANGE=48 QUINTRA_BOT_GIANT_FIRE_CADENCE=2 \
  QUINTRA_BALANCE_REPS=1 QUINTRA_BALANCE_RUNS=1 QUINTRA_BALANCE_CLASSES=1 \
  QUINTRA_BALANCE_FRAMES=18000 QUINTRA_BALANCE_HOST_TIMEOUT=40 \
  QUINTRA_BALANCE_OUT="$FAR" \
  bash "$ROOT/scripts/run_balance_bot.sh" "$ROM" >/dev/null

awk -F, '
  NR == FNR { if (FNR == 1) for (i = 1; i <= NF; ++i) near_col[$i] = i; else near = $(near_col["bosses"]); next }
  FNR == 1 { for (i = 1; i <= NF; ++i) far_col[$i] = i; next }
  { far = $(far_col["bosses"]) }
  END {
    if (near <= far) {
      print "[sauran-boss] explicit near/far search overrides did not change live policy" > "/dev/stderr"
      exit 1
    }
  }
' "$NEAR" "$FAR"

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
    if (bosses < 1) { print "[sauran-boss] classwise policy cleared no first boss" > "/dev/stderr"; exit 1 }
    if (stalled) { print "[sauran-boss] live-combat stall" > "/dev/stderr"; exit 1 }
  }
' "$OUT"
echo "[sauran-boss] PASS paired policy cleared a boss without a stall"
