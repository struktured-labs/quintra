#!/usr/bin/env bash
# Regression: an open early room may leave an optional edge Crawler alive.
# Wolfkin's controller must honour that visible forward exit instead of letting
# combat-only border protection turn it back toward a two-HP target forever.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ROM="${1:-$ROOT/rom/working/quintra.gbc}"
OUT="$(mktemp /tmp/quintra-wolfkin-open-exit.XXXXXX)"
trap 'rm -f "$OUT" "$OUT.lock"' EXIT

# This is an exit-routing fixture, not a boss-survival gate. Use the coarse
# tester assist and require substantial progress beyond the early optional
# boundary; dedicated policy tests own Colossus performance.
QUINTRA_BOT_EASY=1 QUINTRA_BALANCE_RUNS=4 QUINTRA_BALANCE_CLASSES=0 \
  QUINTRA_BALANCE_TARGET_FRAME=460 \
  QUINTRA_BALANCE_FRAMES=70000 QUINTRA_BALANCE_HOST_TIMEOUT=1200 \
  QUINTRA_BALANCE_OUT="$OUT" QUINTRA_BALANCE_SKIP_REPORT=1 \
  bash "$ROOT/scripts/run_balance_bot.sh" "$ROM" >/dev/null

awk -F, '
  NR == 1 { for (i = 1; i <= NF; ++i) col[$i] = i; next }
  {
    rows++
    if ($(col["seed"]) != 2064128647) wrong_seed = 1
    # With Road Echo support now hidden behind exploration, this fixed solo
    # world still proves the optional boundary exit by reaching room 10, but
    # visits seven rather than eight unique cells before later attrition.
    if ($(col["max_room"]) < 10 || $(col["rooms_seen"]) < 7) stuck = 1
  }
  END {
    if (rows != 1) { print "[wolfkin-open-exit] missing fixed controller row" > "/dev/stderr"; exit 1 }
    if (wrong_seed) { print "[wolfkin-open-exit] controller world drifted" > "/dev/stderr"; exit 1 }
    if (stuck) {
      print "[wolfkin-open-exit] optional boundary enemy still prevents forward route" > "/dev/stderr"
      exit 1
    }
  }
' "$OUT"
echo "[wolfkin-open-exit] PASS Wolfkin leaves the unsealed boundary encounter"
