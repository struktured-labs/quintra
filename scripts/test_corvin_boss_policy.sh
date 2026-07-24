#!/usr/bin/env bash
# Regression: Featherbarb's real range supports orbit-and-fire against giants.
# Pin one real title-frame-derived Normal world so this policy contract cannot
# turn into an entropy lottery that dies in an unrelated early encounter
# before reaching the bosses it is meant to exercise.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ROM="${1:-$ROOT/rom/working/quintra.gbc}"
OUT="$(mktemp /tmp/quintra-corvin-boss.XXXXXX)"

# Frame 680 with replay id 27 enters run seed 2064128483 on the current ROM.
# It survives the expanded Sigil/Warden route and reaches a real Normal
# colossus with enough health for the test to isolate orbit pressure instead
# of measuring unrelated route attrition.
QUINTRA_BALANCE_RUNS=27 QUINTRA_BALANCE_CLASSES=2 \
  QUINTRA_BALANCE_FRAMES=14000 QUINTRA_BALANCE_HOST_TIMEOUT=45 \
  QUINTRA_BALANCE_TARGET_FRAME=680 \
  QUINTRA_BALANCE_OUT="$OUT" \
  bash "$ROOT/scripts/run_balance_bot.sh" "$ROM" >/dev/null

awk -F, -v expected_seed=2064128483 '
  NR == 1 {
    for (i = 1; i <= NF; ++i) col[$i] = i
    next
  }
  {
    rows++
    attempts += $(col["boss_attempts"])
    if ($(col["min_giant_hp"]) < min_giant_hp || min_giant_hp == 0)
      min_giant_hp = $(col["min_giant_hp"])
    if ($(col["seed"]) != expected_seed) wrong_seed = 1
    if ($(col["max_target_stall_frames"]) > 3600 && $(col["min_hp"]) > 0)
      stalled = 1
  }
  END {
    if (rows != 1) { print "[corvin-boss] missing deterministic row" > "/dev/stderr"; exit 1 }
    if (wrong_seed) { print "[corvin-boss] fixed controller world drifted" > "/dev/stderr"; exit 1 }
    if (attempts < 1 || min_giant_hp > 20) {
      print "[corvin-boss] orbit policy did not produce a near-clear giant attempt" > "/dev/stderr"
      exit 1
    }
    if (stalled) { print "[corvin-boss] live-combat stall" > "/dev/stderr"; exit 1 }
  }
' "$OUT"
echo "[corvin-boss] PASS fixed Normal orbit policy produced a near-clear giant fight without a stall"
