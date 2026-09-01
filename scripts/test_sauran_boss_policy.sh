#!/usr/bin/env bash
# Regression: Sauran's Tail Spike classwise giant policy must preserve a safe,
# productive pressure lane. Three native checkpoints exercise distinct live
# Colossi without turning this focused policy gate into a dungeon endurance run.
# `max_combat_frames` is
# intentionally not used here: it measures whole procedural-room age, not a
# no-progress interval, and can include several legitimate sequential fights.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ROM="${1:-$ROOT/rom/working/quintra.gbc}"
OUT="$(mktemp /tmp/quintra-sauran-boss.XXXXXX)"

for replay in '11 01' '12 02' '13 05'; do
  read -r run stage <<EOF
$replay
EOF
  STATE="$ROOT/tmp/mgba-states-smoke/quintra-stage-${stage}-boss-sauran-easy.ss0"
  test -s "$STATE"
  QUINTRA_MGBA_STATE="$STATE" QUINTRA_BALANCE_RESUME_STATE=1 \
    QUINTRA_BOT_EASY=1 QUINTRA_BALANCE_RUNS="$run" QUINTRA_BALANCE_CLASSES=1 \
    QUINTRA_BALANCE_FRAMES=12000 QUINTRA_BALANCE_HOST_TIMEOUT=900 \
    QUINTRA_BALANCE_OUT="$OUT" QUINTRA_BALANCE_APPEND=1 \
    QUINTRA_BALANCE_SKIP_REPORT=1 \
    bash "$ROOT/scripts/run_balance_bot.sh" "$ROM" >/dev/null
done

awk -F, '
  NR == 1 {
    for (i = 1; i <= NF; ++i) col[$i] = i
    next
  }
  {
    rows++
    if ($(col["boss_attempts"]) >= 1 && $(col["boss_clear_frames"]) > 0)
      clears++
    if ($(col["death_source"]) != 255 && $(col["boss_clear_frames"]) == 0)
      early_deaths++
  }
  END {
    if (rows != 3) { print "[sauran-boss] missing paired rows" > "/dev/stderr"; exit 1 }
    if (clears != 3) { print "[sauran-boss] classwise policy did not clear all three Colossi" > "/dev/stderr"; exit 1 }
    if (early_deaths > 0) { print "[sauran-boss] classwise policy died before an opening clear" > "/dev/stderr"; exit 1 }
  }
' "$OUT"
echo "[sauran-boss] PASS Easy policy cleared three distinct live Colossi"
