#!/usr/bin/env bash
# Regression: Vespine's close Stinger benefits from the measured pulse-fire
# giant lane. Paired baseline cleared one first boss; classwise play must
# retain at least two. `max_combat_frames` is a whole-room dwell measure, so
# a later cleared multi-enemy room is not treated as a boss-policy stall here.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ROM="${1:-$ROOT/rom/working/quintra.gbc}"
OUT="$(mktemp /tmp/quintra-vespine-boss.XXXXXX)"

for replay in '1 440 2064128755' '2 540 2064128343' '3 400 2064128731'; do
  read -r run frame seed <<EOF
$replay
EOF
  QUINTRA_BALANCE_RUNS="$run" QUINTRA_BALANCE_CLASSES=4 \
    QUINTRA_BALANCE_TARGET_FRAME="$frame" \
    QUINTRA_BALANCE_FRAMES=18000 QUINTRA_BALANCE_HOST_TIMEOUT=60 \
    QUINTRA_MGBA_SAVE_DIR="${OUT}.save" QUINTRA_BALANCE_OUT="$OUT" \
    QUINTRA_BALANCE_APPEND=1 QUINTRA_BALANCE_SKIP_REPORT=1 \
    bash "$ROOT/scripts/run_balance_bot.sh" "$ROM" >/dev/null
done

awk -F, '
  NR == 1 {
    for (i = 1; i <= NF; ++i) col[$i] = i
    next
  }
  {
    rows++
    if ($(col["seed"]) != (NR == 2 ? 2064128755 : NR == 3 ? 2064128343 : 2064128731))
      wrong_seed = 1
    bosses += $(col["bosses"])
  }
  END {
    if (rows != 3) { print "[vespine-boss] missing paired rows" > "/dev/stderr"; exit 1 }
    if (wrong_seed) { print "[vespine-boss] fixed controller world drifted" > "/dev/stderr"; exit 1 }
    if (bosses < 2) { print "[vespine-boss] classwise policy cleared fewer than two bosses" > "/dev/stderr"; exit 1 }
  }
' "$OUT"
echo "[vespine-boss] PASS paired policy cleared two bosses"
