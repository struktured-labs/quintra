#!/usr/bin/env bash
# Regression: Picsean's full-room BubbleBolt must exploit Frost Spider's
# post-blink lane instead of re-entering the web at short orbit range. This
# fixed real-input sample clears the fifth boss alive across the expanded
# seven-role topology; full nine-boss victory remains covered by its stricter
# separate replay. Easy is setup only and leaves weapon geometry, blink
# behavior, Will, and signature costs unchanged.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ROM="${1:-$ROOT/rom/working/quintra.gbc}"
OUT="$(mktemp /tmp/quintra-picsean-frost-lane.XXXXXX)"
trap 'rm -f "$OUT" "$OUT.lock"' EXIT

QUINTRA_BOT_EASY=1 QUINTRA_BALANCE_RUNS=4 QUINTRA_BALANCE_CLASSES=3 \
  QUINTRA_BALANCE_REPS=1 QUINTRA_BALANCE_TARGET_FRAME=1000 \
  QUINTRA_BOT_THREAT_POLICY=proximity \
  QUINTRA_BALANCE_FRAMES=200000 QUINTRA_BALANCE_HOST_TIMEOUT=500 \
  QUINTRA_BALANCE_OUT="$OUT" QUINTRA_BALANCE_SKIP_REPORT=1 \
  bash "$ROOT/scripts/run_balance_bot.sh" "$ROM" >/dev/null

awk -F, '
  NR == 1 {
    for (i = 1; i <= NF; ++i) col[$i] = i
    next
  }
  {
    rows++
    if ($(col["seed"]) != 2064128163) wrong_seed = 1
    if ($(col["bosses"]) < 5 || $(col["max_room"]) < 129) missed_lane = 1
    if ($(col["death_room"]) == 24 && $(col["death_bosses"]) == 3) died_frost = 1
  }
  END {
    if (rows != 1) { print "[picsean-frost-lane] missing deterministic row" > "/dev/stderr"; exit 1 }
    if (wrong_seed) { print "[picsean-frost-lane] fixed world drifted" > "/dev/stderr"; exit 1 }
    if (missed_lane || died_frost) {
      print "[picsean-frost-lane] BubbleBolt failed Frost post-blink lane" > "/dev/stderr"
      exit 1
    }
  }
' "$OUT"
echo "[picsean-frost-lane] PASS BubbleBolt clears Frost and reaches boss five"
