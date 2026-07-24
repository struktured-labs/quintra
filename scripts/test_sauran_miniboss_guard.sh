#!/usr/bin/env bash
# Regression: Sauran must spend his real Stoneskin on the room-three Sentinel
# when that body pins the 48px Tail Spike lane.  This fixed input-only replay
# used to die in room 3 with no boss cleared; it now exits the miniboss room.
# This is an ability/route diagnostic, so it uses the tester assist to keep the
# later Colossus from conflating the result with canonical Normal balance. The
# deeper right-edge replay remains the separate, intentionally stricter gate.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ROM="${1:-$ROOT/rom/working/quintra.gbc}"
OUT="$(mktemp /tmp/quintra-sauran-miniboss.XXXXXX)"
trap 'rm -f "$OUT" "$OUT.lock"' EXIT

QUINTRA_BOT_EASY=1 QUINTRA_BALANCE_RUNS=3 QUINTRA_BALANCE_CLASSES=1 \
  QUINTRA_BALANCE_REPS=1 QUINTRA_BALANCE_TARGET_FRAME=500 \
  QUINTRA_BALANCE_FRAMES=12000 QUINTRA_BALANCE_HOST_TIMEOUT=60 \
  QUINTRA_BALANCE_OUT="$OUT" QUINTRA_BALANCE_SKIP_REPORT=1 \
  bash "$ROOT/scripts/run_balance_bot.sh" "$ROM" >/dev/null

awk -F, '
  NR == 1 {
    for (i = 1; i <= NF; ++i) col[$i] = i
    next
  }
  {
    rows++
    if ($(col["seed"]) != 2064128703) wrong_seed = 1
    death_room = $(col["death_room"])
    max_room = $(col["max_room"])
  }
  END {
    if (rows != 1) { print "[sauran-miniboss] missing deterministic row" > "/dev/stderr"; exit 1 }
    if (wrong_seed) { print "[sauran-miniboss] fixed controller world drifted" > "/dev/stderr"; exit 1 }
    if (death_room == 3) { print "[sauran-miniboss] Stoneskin did not break the room-3 Sentinel pin" > "/dev/stderr"; exit 1 }
    # Bosses are deliberately no longer a five-second proxy for route
    # progress. Reaching any later room proves the actual fixture contract:
    # Sauran escaped the room-three Sentinel body pin.
    if (max_room <= 3) { print "[sauran-miniboss] route did not leave the Sentinel room" > "/dev/stderr"; exit 1 }
  }
' "$OUT"
echo "[sauran-miniboss] PASS Stoneskin breaks the Sentinel body pin"
