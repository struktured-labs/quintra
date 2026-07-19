#!/usr/bin/env bash
# Regression: a controller that takes room-2's nonlinear rift before claiming
# its Sigil must use the paired room-4 rift to return. Portal arrivals have no
# cardinal ``entered_from`` direction, so a generic back-door policy once
# wandered the merchant/sanctuary loop for over a minute. This fixed Picsean
# seed reaches the real branch through normal controller input.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ROM="${1:-$ROOT/rom/working/quintra.gbc}"
OUT="$(mktemp /tmp/quintra-sigil-return.XXXXXX)"

QUINTRA_BALANCE_RUNS=1 QUINTRA_BALANCE_CLASSES=3 \
  QUINTRA_BALANCE_TARGET_FRAME=346 QUINTRA_BALANCE_FRAMES=15000 \
  QUINTRA_BALANCE_HOST_TIMEOUT=50 \
  QUINTRA_BALANCE_OUT="$OUT" \
  bash "$ROOT/scripts/run_balance_bot.sh" "$ROM" >/dev/null

awk -F, '
  NR == 1 {
    for (i = 1; i <= NF; ++i) col[$i] = i
    next
  }
  NR == 2 {
    if ($(col["seed"]) != 2064128529) {
      print "[sigil-return] fixed controller seed drifted" > "/dev/stderr"
      exit 1
    }
    if ($(col["max_room"]) < 6) {
      print "[sigil-return] did not leave the locked sanctuary" > "/dev/stderr"
      exit 1
    }
    if ($(col["max_route_frames"]) > 3600) {
      print "[sigil-return] route stall after missing Sigil" > "/dev/stderr"
      exit 1
    }
    found = 1
  }
  END {
    if (!found) {
      print "[sigil-return] missing controller row" > "/dev/stderr"
      exit 1
    }
  }
' "$OUT"
echo "[sigil-return] PASS missing-Sigil sanctuary was backtracked without a route stall"
