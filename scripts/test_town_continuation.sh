#!/usr/bin/env bash
# Regression: a long-form controller run that reaches the three-screen town
# must take its north gate into the next dungeon rather than pacing at the
# gate lip. This paired Picsean seed reaches the town after the controller's
# deliberate market + forge/apothecary detour.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ROM="${1:-$ROOT/rom/working/quintra.gbc}"
OUT="$(mktemp /tmp/quintra-town-continuation.XXXXXX)"

# This is a town-geometry/controller fixture, not a combat-balance gate.
# Keep its route stable with the coarse tester assist while Normal remains
# covered by the dedicated boss and whole-run victory policies.
QUINTRA_BOT_EASY=1 QUINTRA_BALANCE_RUNS=1 QUINTRA_BALANCE_CLASSES=3 \
  QUINTRA_BALANCE_FRAMES=45000 QUINTRA_BALANCE_HOST_TIMEOUT=120 \
  QUINTRA_BALANCE_TARGET_FRAME=1000 QUINTRA_BOT_THREAT_POLICY=collision \
  QUINTRA_BALANCE_OUT="$OUT" \
  bash "$ROOT/scripts/run_balance_bot.sh" "$ROM" >/dev/null

awk -F, '
  NR == 1 {
    for (i = 1; i <= NF; ++i) col[$i] = i
    next
  }
  NR == 2 {
    found = 1
    if ($(col["towns"]) < 1) {
      print "[town-continuation] did not reach the town" > "/dev/stderr"
      exit 1
    }
    if ($(col["town_market_visits"]) < 1 || $(col["town_quarter_visits"]) < 1) {
      print "[town-continuation] did not visit both town build-choice screens" > "/dev/stderr"
      exit 1
    }
    # The expanded town-45 north gate enters room 46, the first room of the
    # next dungeon. Requiring later cells would accidentally couple this gate
    # to surviving two subsequent randomized combat rooms and to whichever
    # optional weapon build the controller happened to take.
    if ($(col["max_room"]) < 46) {
      print "[town-continuation] north gate did not continue the run" > "/dev/stderr"
      exit 1
    }
    # `max_route_frames` covers the rest of the run too. Only a prolonged
    # dwell in room 45 is evidence that the actual town north gate failed;
    # a later procedural dungeon route must not be mislabeled as this gate.
    if ($(col["max_route_room"]) == 45 && $(col["max_route_frames"]) > 3600) {
      print "[town-continuation] town north-gate route stall" > "/dev/stderr"
      exit 1
    }
  }
  END {
    if (!found) {
      print "[town-continuation] missing controller row" > "/dev/stderr"
      exit 1
    }
  }
' "$OUT"
echo "[town-continuation] PASS north civic lane reaches the next dungeon"
