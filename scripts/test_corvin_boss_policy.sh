#!/usr/bin/env bash
# Regression: Featherbarb's real range supports orbit-and-fire against giants.
# Begin at the release gate's native boss checkpoint so this policy cannot
# spend its entire budget orbiting an unrelated dense opening-room formation.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ROM="${1:-$ROOT/rom/working/quintra.gbc}"
OUT="$(mktemp /tmp/quintra-corvin-boss.XXXXXX)"
STATE="$ROOT/tmp/mgba-states-smoke/quintra-stage-01-boss-corvin-easy.ss0"
test -s "$STATE"

# The checkpoint supplies progression only. Boss movement, arena projectiles,
# HP, and every subsequent action remain live cartridge/controller behavior.
QUINTRA_MGBA_STATE="$STATE" QUINTRA_BALANCE_RESUME_STATE=1 \
  QUINTRA_BOT_EASY=1 QUINTRA_BALANCE_RUNS=27 QUINTRA_BALANCE_CLASSES=2 \
  QUINTRA_BALANCE_FRAMES=10000 QUINTRA_BALANCE_HOST_TIMEOUT=600 \
  QUINTRA_BALANCE_OUT="$OUT" \
  bash "$ROOT/scripts/run_balance_bot.sh" "$ROM" >/dev/null

awk -F, '
  NR == 1 {
    for (i = 1; i <= NF; ++i) col[$i] = i
    next
  }
  {
    rows++
    attempts += $(col["boss_attempts"])
    if ($(col["min_giant_hp"]) < min_giant_hp || min_giant_hp == 0)
      min_giant_hp = $(col["min_giant_hp"])
    if ($(col["max_target_stall_frames"]) > 3600 && $(col["min_hp"]) > 0)
      stalled = 1
  }
  END {
    if (rows != 1) { print "[corvin-boss] missing deterministic row" > "/dev/stderr"; exit 1 }
    if (attempts < 1 || min_giant_hp > 20) {
      print "[corvin-boss] orbit policy did not produce a near-clear giant attempt" > "/dev/stderr"
      exit 1
    }
    if (stalled) { print "[corvin-boss] live-combat stall" > "/dev/stderr"; exit 1 }
  }
' "$OUT"
echo "[corvin-boss] PASS fixed orbit policy produced a near-clear giant fight without a stall"
