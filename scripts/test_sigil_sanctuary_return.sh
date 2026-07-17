#!/usr/bin/env bash
# Regression: a controller that reaches the Sigil-gated sanctuary without its
# stage objective must retrace to the fixture instead of pressing the locked
# forward doorway forever. This paired Picsean seed is deliberately the
# controller-stable probe: the short-range/tank pilots can die in the room-3
# miniboss before they exercise the sanctuary branch, making them a combat
# test rather than a navigation regression.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ROM="${1:-$ROOT/rom/working/quintra.gbc}"
OUT="$(mktemp /tmp/quintra-sigil-return.XXXXXX)"

QUINTRA_BALANCE_RUNS=0 QUINTRA_BALANCE_CLASSES=3 \
  QUINTRA_BALANCE_FRAMES=12000 QUINTRA_BALANCE_HOST_TIMEOUT=40 \
  QUINTRA_BALANCE_OUT="$OUT" \
  bash "$ROOT/scripts/run_balance_bot.sh" "$ROM" >/dev/null

awk -F, '
  NR == 1 {
    for (i = 1; i <= NF; ++i) col[$i] = i
    next
  }
  NR == 2 {
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
