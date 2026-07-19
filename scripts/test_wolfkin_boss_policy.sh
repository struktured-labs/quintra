#!/usr/bin/env bash
# Regression: Wolfkin's adjacent Claw needs a measured orbit-fire giant lane
# and a contact-range Howl. On paired deterministic seeds, each route must
# now clear three bosses without a live-combat stall; spending Howl before its
# ring could connect left the real-melee pilot without its activation ward.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ROM="${1:-$ROOT/rom/working/quintra.gbc}"
OUT="$(mktemp /tmp/quintra-wolfkin-boss.XXXXXX)"

QUINTRA_BALANCE_REPS=3 QUINTRA_BALANCE_CLASSES=0 \
  QUINTRA_BALANCE_FRAMES=18000 QUINTRA_BALANCE_HOST_TIMEOUT=40 \
  QUINTRA_BALANCE_OUT="$OUT" \
  bash "$ROOT/scripts/run_balance_bot.sh" "$ROM" >/dev/null

awk -F, '
  NR == 1 {
    for (i = 1; i <= NF; ++i) col[$i] = i
    next
  }
  {
    rows++
    bosses += $(col["bosses"])
    if ($(col["bosses"]) < 3)
      weak = 1
    if ($(col["max_combat_frames"]) > 3600 && $(col["min_hp"]) > 0)
      stalled = 1
  }
  END {
    if (rows != 3) { print "[wolfkin-boss] missing paired rows" > "/dev/stderr"; exit 1 }
    if (weak || bosses < 9) { print "[wolfkin-boss] a paired route did not clear three bosses" > "/dev/stderr"; exit 1 }
    if (stalled) { print "[wolfkin-boss] live-combat stall" > "/dev/stderr"; exit 1 }
  }
' "$OUT"
echo "[wolfkin-boss] PASS all paired routes cleared three bosses without a stall"
