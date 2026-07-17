#!/usr/bin/env bash
# The final Void Sanctum Sigil once exposed the pilot's tile-vs-pixel route
# mismatch. This is a controller-only completion proof: it drives the public
# D-pad/A/B inputs on the actual seed-14 cartridge and requires all nine
# bosses, not merely a debugger-side room reachability check.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ROM="${1:-$ROOT/rom/working/quintra.gbc}"
TMP="$(mktemp -d /tmp/quintra-final-sigil-controller.XXXXXX)"
CSV="$TMP/run.csv"

QUINTRA_BALANCE_RUNS=14 QUINTRA_BALANCE_CLASSES=3 \
  QUINTRA_BALANCE_FRAMES=90000 QUINTRA_BALANCE_HOST_TIMEOUT=180 \
  QUINTRA_MGBA_SAVE_DIR="$TMP/save" QUINTRA_BALANCE_OUT="$CSV" \
  bash "$ROOT/scripts/run_balance_bot.sh" "$ROM" >/dev/null

awk -F, '
  NR == 1 { for (i = 1; i <= NF; ++i) col[$i] = i; next }
  NR == 2 {
    if ($(col["victory"]) != 1 || $(col["bosses"]) != 9 || $(col["frames"]) >= 90000) {
      print "[final-sigil-controller] seed 14 did not finish" > "/dev/stderr"
      exit 1
    }
    printf "[final-sigil-controller] PASS seed 14 bosses=%s frames=%s\n", \
      $(col["bosses"]), $(col["frames"])
    found = 1
  }
  END { if (!found) exit 1 }
' "$CSV"
