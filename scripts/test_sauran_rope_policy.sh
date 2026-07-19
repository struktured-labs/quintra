#!/usr/bin/env bash
# Regression: a real Tail Spike is a 48px lunge.  On deterministic run two,
# the controller used to pursue a Rope at room seven's north wall as though it
# were Wolfkin's adjacent claw, creating an artificial multi-thousand-frame
# combat stall.  This observes only controller input and ROM telemetry.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ROM="${1:-$ROOT/rom/working/quintra.gbc}"
OUT="$(mktemp /tmp/quintra-sauran-rope.XXXXXX)"

QUINTRA_BALANCE_RUNS=2 QUINTRA_BALANCE_CLASSES=1 \
  QUINTRA_BALANCE_FRAMES=12000 QUINTRA_BALANCE_HOST_TIMEOUT=40 \
  QUINTRA_BALANCE_OUT="$OUT" QUINTRA_BALANCE_SKIP_REPORT=1 \
  bash "$ROOT/scripts/run_balance_bot.sh" "$ROM" >/dev/null

awk -F, '
  NR == 1 {
    for (i = 1; i <= NF; ++i) col[$i] = i
    next
  }
  {
    rows++
    if ($(col["max_room"]) < 8) escaped = 0
    else escaped = 1
    if ($(col["max_combat_frames"]) > 3600 && $(col["min_hp"]) > 0)
      stalled = 1
  }
  END {
    if (rows != 1) { print "[sauran-rope] missing deterministic row" > "/dev/stderr"; exit 1 }
    if (!escaped) { print "[sauran-rope] did not leave Rope room" > "/dev/stderr"; exit 1 }
    if (stalled) { print "[sauran-rope] Tail Spike controller stalled" > "/dev/stderr"; exit 1 }
  }
' "$OUT"
echo "[sauran-rope] PASS Tail Spike leaves the north-wall Rope lane"
