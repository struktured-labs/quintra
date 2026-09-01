#!/usr/bin/env bash
# Regression: Vespine's Stinger route used to let a wall-adjacent Rope drain
# the entire run. The controller must spend its real double-tap dash after the
# observed body hit and leave a Rope encounter rather than merely avoiding a
# combat-stall classification. The former run-32 room-7 sample now dies before
# the first boss because the expanded maze correctly removed its row
# shortcuts; use the paired long-wing sample that demonstrably encounters a
# Rope and advances to the Colossus threshold. Easy preserves the Rope's
# movement and body-pin geometry while the direct boss checkpoint owns giant
# performance separately.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ROM="${1:-$ROOT/rom/working/quintra.gbc}"
TMP="$(mktemp -d /tmp/quintra-vespine-rope.XXXXXX)"
trap 'rm -rf "$TMP"' EXIT
OUT="$TMP/run.csv"

# The seven-role dependency chain makes this a long Rope route. The tester
# assist preserves its movement and body-pin geometry.
QUINTRA_BOT_EASY=1 QUINTRA_BALANCE_RUNS=2 QUINTRA_BALANCE_CLASSES=4 \
  QUINTRA_BALANCE_TARGET_FRAME=540 \
  QUINTRA_BALANCE_FRAMES=32000 QUINTRA_BALANCE_HOST_TIMEOUT=900 \
  QUINTRA_BALANCE_TRACE_DIR="$TMP/traces" QUINTRA_BALANCE_OUT="$OUT" \
  bash "$ROOT/scripts/run_balance_bot.sh" "$ROM" >/dev/null

awk -F, '
  NR == 1 {
    for (i = 1; i <= NF; ++i) col[$i] = i
    next
  }
  NR == 2 {
    if ($(col["seed"]) != 2064128343) {
      print "[vespine-rope] fixed controller world drifted" > "/dev/stderr"
      exit 1
    }
    if (and($(col["enemy_mask"]), 512) == 0) {
      print "[vespine-rope] deterministic Rope was not observed" > "/dev/stderr"
      exit 1
    }
    if ($(col["death_source"]) == 9) {
      print "[vespine-rope] Rope still ended the run" > "/dev/stderr"
      exit 1
    }
  }
  END {
    if (NR != 2) {
      print "[vespine-rope] missing deterministic result" > "/dev/stderr"
      exit 1
    }
  }
' "$OUT"

OBS="$TMP/traces/run-2-class-4-1.obs.csv"
awk -F, '
  NR == 2 { sub(/^# /, ""); for (i = 1; i <= NF; ++i) col[$i] = i; next }
  NR > 2 && !seen && $(col["target_kind"]) == 9 {
    seen = 1; rope_room = $(col["room"])
  }
  NR > 2 && seen && $(col["room"]) != rope_room { escaped = 1 }
  END {
    if (!seen || !escaped) {
      print "[vespine-rope] did not escape the deterministic Rope lane" > "/dev/stderr"
      exit 1
    }
  }
' "$OBS"
echo "[vespine-rope] PASS body-dash escapes the deterministic Rope pin"
