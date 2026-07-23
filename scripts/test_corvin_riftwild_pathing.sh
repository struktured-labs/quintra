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

# Outdoor collision/pathing is identical in Easy; use the tester budget so
# the harder opening boss cannot prevent this traversal fixture from running.
QUINTRA_BOT_EASY=1 QUINTRA_BALANCE_RUNS=3 QUINTRA_BALANCE_CLASSES=2 \
  QUINTRA_BALANCE_FRAMES=12000 QUINTRA_BALANCE_HOST_TIMEOUT=40 \
  QUINTRA_BALANCE_OUT="$OUT" \
  bash "$ROOT/scripts/run_balance_bot.sh" "$ROM" >/dev/null

awk -F, '
  NR == 1 {
    for (i = 1; i <= NF; ++i) col[$i] = i
    next
  }
  NR == 2 {
    if ($(col["max_room"]) < 12 || $(col["world_hops"]) < 5) {
      print "[corvin-riftwild] did not cross the outdoor graph" > "/dev/stderr"
      exit 1
    }
    if ($(col["max_route_frames"]) > 3600 && $(col["min_hp"]) > 0) {
      print "[corvin-riftwild] live route stall" > "/dev/stderr"
      exit 1
    }
    found = 1
  }
  END {
    if (!found) {
      print "[corvin-riftwild] missing deterministic row" > "/dev/stderr"
      exit 1
    }
  }
' "$OUT"
echo "[corvin-riftwild] PASS Corvin crosses the Riftwild grass route"
