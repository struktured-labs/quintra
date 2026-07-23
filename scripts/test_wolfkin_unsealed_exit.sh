#!/usr/bin/env bash
# Regression: an open early room may leave an optional edge Crawler alive.
# Wolfkin's controller must honour that visible forward exit instead of letting
# combat-only border protection turn it back toward a two-HP target forever.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ROM="${1:-$ROOT/rom/working/quintra.gbc}"
OUT="$(mktemp /tmp/quintra-wolfkin-open-exit.XXXXXX)"
trap 'rm -f "$OUT" "$OUT.lock"' EXIT

# The Penta-scale first two colossi now consume more of the deterministic
# replay than the former small bosses. Keep the route assertion unchanged,
# but give the controller enough frames to traverse the new 20/21-room first
# pair and reach the later optional boundary encounter this contract
# actually exercises.
# This is an exit-routing fixture. Use the coarse tester assist so surviving
# two colossal bosses is only its setup, not an accidental Normal-balance
# requirement.
QUINTRA_BOT_EASY=1 QUINTRA_BALANCE_RUNS=4 QUINTRA_BALANCE_CLASSES=0 \
  QUINTRA_BALANCE_TARGET_FRAME=460 \
  QUINTRA_BALANCE_FRAMES=24000 QUINTRA_BALANCE_HOST_TIMEOUT=70 \
  QUINTRA_BALANCE_OUT="$OUT" QUINTRA_BALANCE_SKIP_REPORT=1 \
  bash "$ROOT/scripts/run_balance_bot.sh" "$ROM" >/dev/null

awk -F, '
  NR == 1 { for (i = 1; i <= NF; ++i) col[$i] = i; next }
  {
    rows++
    if ($(col["seed"]) != 2064128647) wrong_seed = 1
    if ($(col["max_room"]) < 20) stuck = 1
    if ($(col["bosses"]) < 2) no_progress = 1
  }
  END {
    if (rows != 1) { print "[wolfkin-open-exit] missing fixed controller row" > "/dev/stderr"; exit 1 }
    if (wrong_seed) { print "[wolfkin-open-exit] controller world drifted" > "/dev/stderr"; exit 1 }
    if (stuck || no_progress) {
      print "[wolfkin-open-exit] optional boundary enemy still prevents forward route" > "/dev/stderr"
      exit 1
    }
  }
' "$OUT"
echo "[wolfkin-open-exit] PASS Wolfkin leaves the unsealed boundary encounter"
