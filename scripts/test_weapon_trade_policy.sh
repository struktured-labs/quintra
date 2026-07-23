#!/usr/bin/env bash
# Regression: the controller may choose a red weapon orb, but must never
# accidentally confirm it while attacking through the room-three hoard. This
# fixed Sauran replay reaches that orb; it pins the input-side pre-overlap
# guard without changing the cartridge's intentional A-to-trade player rule.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ROM="${1:-$ROOT/rom/working/quintra.gbc}"
OUT="$(mktemp /tmp/quintra-weapon-trade-policy.XXXXXX)"
trap 'rm -f "$OUT" "$OUT.lock"' EXIT

QUINTRA_BALANCE_RUNS=3 QUINTRA_BALANCE_CLASSES=1 \
  QUINTRA_BALANCE_REPS=1 QUINTRA_BALANCE_TARGET_FRAME=480 \
  QUINTRA_BALANCE_FRAMES=6500 QUINTRA_BALANCE_HOST_TIMEOUT=40 \
  QUINTRA_BALANCE_OUT="$OUT" QUINTRA_BALANCE_SKIP_REPORT=1 \
  bash "$ROOT/scripts/run_balance_bot.sh" "$ROM" >/dev/null

awk -F, '
  NR == 1 {
    for (i = 1; i <= NF; ++i) col[$i] = i
    next
  }
  {
    rows++
    if ($(col["seed"]) != 2064128683) wrong_seed = 1
    if ($(col["final_weapon"]) != 1 || $(col["weapon_swaps"]) != 0) traded = 1
  }
  END {
    if (rows != 1) { print "[weapon-trade-policy] missing fixed controller row" > "/dev/stderr"; exit 1 }
    if (wrong_seed) { print "[weapon-trade-policy] controller world drifted" > "/dev/stderr"; exit 1 }
    if (traded) { print "[weapon-trade-policy] pilot accidentally confirmed a weapon trade" > "/dev/stderr"; exit 1 }
  }
' "$OUT"
echo "[weapon-trade-policy] PASS Sauran retains Tail Spike through red-orb crossing"
