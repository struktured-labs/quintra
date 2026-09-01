#!/usr/bin/env bash
# Regression: the controller's collision mirror must recognize the ROM's
# Riftwild grass and path tiles.  Seed three Corvin used to treat both as
# solid, remain on the first outdoor screen, and die to a Hornet before the
# next dungeon.  The agent may still lose the following boss; this checks the
# narrower traversal claim without hiding that combat result.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ROM="${1:-$ROOT/rom/working/quintra.gbc}"
OUT="$(mktemp /tmp/quintra-corvin-riftwild.XXXXXX)"
STATE="$ROOT/tmp/mgba-states-smoke/quintra-riftwild-after-stage-01-corvin-easy.ss0"
test -s "$STATE"

# The checkpoint supplies only the completed opening boss. Riftwild terrain,
# Warden combat, gate travel, and every controller input remain live.
QUINTRA_MGBA_STATE="$STATE" QUINTRA_BALANCE_RESUME_STATE=1 \
  QUINTRA_BOT_EASY=1 QUINTRA_BALANCE_RUNS=3 QUINTRA_BALANCE_CLASSES=2 \
  QUINTRA_BALANCE_FRAMES=8000 QUINTRA_BALANCE_HOST_TIMEOUT=900 \
  QUINTRA_BALANCE_OUT="$OUT" \
  bash "$ROOT/scripts/run_balance_bot.sh" "$ROM" >/dev/null

awk -F, '
  NR == 1 {
    for (i = 1; i <= NF; ++i) col[$i] = i
    next
  }
  NR == 2 {
    found = 1
    if ($(col["max_room"]) < 12 || $(col["world_hops"]) < 5) {
      print "[corvin-riftwild] did not cross the outdoor graph" > "/dev/stderr"
      exit 1
    }
    if ($(col["max_route_frames"]) > 3600 && $(col["min_hp"]) > 0) {
      print "[corvin-riftwild] live route stall" > "/dev/stderr"
      exit 1
    }
  }
  END {
    if (!found) {
      print "[corvin-riftwild] missing deterministic row" > "/dev/stderr"
      exit 1
    }
  }
' "$OUT"
echo "[corvin-riftwild] PASS Corvin crosses the Riftwild grass route"
