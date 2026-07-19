#!/usr/bin/env bash
# Regression: Sauran's Tail Spike classwise giant policy must preserve a safe,
# productive pressure lane. Three fixed fresh-SRAM worlds must each clear a
# first boss, together clear at least four giants, and incur no more than one
# player death. A run number by itself samples title-idle entropy and is not a
# repeatable controller regression.
# `max_combat_frames` is
# intentionally not used here: it measures whole procedural-room age, not a
# no-progress interval, and can include several legitimate sequential fights.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ROM="${1:-$ROOT/rom/working/quintra.gbc}"
OUT="$(mktemp /tmp/quintra-sauran-boss.XXXXXX)"

for replay in '1 520 2064128323' '2 540 2064128343' '3 560 2064128379'; do
  read -r run frame seed <<EOF
$replay
EOF
  QUINTRA_BALANCE_RUNS="$run" QUINTRA_BALANCE_CLASSES=1 \
    QUINTRA_BALANCE_TARGET_FRAME="$frame" \
    QUINTRA_BALANCE_FRAMES=18000 QUINTRA_BALANCE_HOST_TIMEOUT=40 \
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
    if ($(col["seed"]) != (NR == 2 ? 2064128323 : NR == 3 ? 2064128343 : 2064128379))
      wrong_seed = 1
    bosses += $(col["bosses"])
    if ($(col["bosses"]) >= 1) first_bosses++
    if ($(col["death_source"]) != 255) deaths++
  }
  END {
    if (rows != 3) { print "[sauran-boss] missing paired rows" > "/dev/stderr"; exit 1 }
    if (wrong_seed) { print "[sauran-boss] fixed controller world drifted" > "/dev/stderr"; exit 1 }
    if (first_bosses != 3) { print "[sauran-boss] classwise policy missed a first boss" > "/dev/stderr"; exit 1 }
    if (bosses < 4) { print "[sauran-boss] classwise policy cleared fewer than four giants" > "/dev/stderr"; exit 1 }
    if (deaths > 1) { print "[sauran-boss] classwise policy caused too many player deaths" > "/dev/stderr"; exit 1 }
  }
' "$OUT"
echo "[sauran-boss] PASS paired policy cleared every first boss and four giants with at most one death"
