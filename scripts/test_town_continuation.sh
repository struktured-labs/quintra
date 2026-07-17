#!/usr/bin/env bash
# Regression: a long-form controller run that reaches the three-screen town
# must take its north gate into the next dungeon rather than pacing at the
# gate lip. This paired Picsean seed formerly idled in room 19 for 11k frames.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ROM="${1:-$ROOT/rom/working/quintra.gbc}"
OUT="$(mktemp /tmp/quintra-town-continuation.XXXXXX)"

QUINTRA_BALANCE_RUNS=4 QUINTRA_BALANCE_CLASSES=3 \
  QUINTRA_BALANCE_FRAMES=24000 QUINTRA_BALANCE_HOST_TIMEOUT=60 \
  QUINTRA_BALANCE_OUT="$OUT" \
  bash "$ROOT/scripts/run_balance_bot.sh" "$ROM" >/dev/null

awk -F, '
  NR == 1 {
    for (i = 1; i <= NF; ++i) col[$i] = i
    next
  }
  NR == 2 {
    if ($(col["towns"]) < 1) {
      print "[town-continuation] did not reach the town" > "/dev/stderr"
      exit 1
    }
    if ($(col["max_room"]) < 22) {
      print "[town-continuation] north gate did not continue the run" > "/dev/stderr"
      exit 1
    }
    if ($(col["max_route_frames"]) > 3600) {
      print "[town-continuation] town route stall" > "/dev/stderr"
      exit 1
    }
    found = 1
  }
  END {
    if (!found) {
      print "[town-continuation] missing controller row" > "/dev/stderr"
      exit 1
    }
  }
' "$OUT"
echo "[town-continuation] PASS north civic lane reaches the next dungeon"
