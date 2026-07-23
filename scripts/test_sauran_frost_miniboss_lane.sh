#!/usr/bin/env bash
# Regression: the fixed Sauran route reaches Frost Vault's covered Sentinel
# after Cinder.  Its body-valid Tail Spike lane can require a sustained BFS
# recovery; generic dodge/shield priorities must not turn that into an
# indefinite room-21 stall.  This is deliberately narrower than the separate
# seven-boss endurance gate, which remains a release-facing balance target.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ROM="${1:-$ROOT/rom/working/quintra.gbc}"
OUT="$(mktemp /tmp/quintra-sauran-frost-lane.XXXXXX)"
trap 'rm -f "$OUT" "$OUT.lock"' EXIT

# Use a measured Easy route for this deep lane fixture. Enemy layout and AI
# remain identical; only the tester's stats keep earlier colossi from masking
# whether the covered Frost Sentinel route itself works.
# Pin the synchronized room handoff for this fixed-world controller fixture.
# At 52 recovery frames the route reaches room 24 after clearing the covered
# room-21 Sentinel; changing it deliberately requires re-measuring this lane.
QUINTRA_BOT_EASY=1 QUINTRA_BOT_READY_IFRAMES=52 \
  QUINTRA_BALANCE_RUNS=2 QUINTRA_BALANCE_CLASSES=1 \
  QUINTRA_BALANCE_REPS=1 QUINTRA_BALANCE_TARGET_FRAME=540 \
  QUINTRA_BALANCE_FRAMES=36000 QUINTRA_BALANCE_HOST_TIMEOUT=90 \
  QUINTRA_BALANCE_OUT="$OUT" QUINTRA_BALANCE_SKIP_REPORT=1 \
  bash "$ROOT/scripts/run_balance_bot.sh" "$ROM" >/dev/null

awk -F, '
  NR == 1 {
    for (i = 1; i <= NF; ++i) col[$i] = i
    next
  }
  {
    rows++
    if ($(col["seed"]) != 2064128343) wrong_seed = 1
    if ($(col["max_room"]) < 24) missed_frost = 1
    if ($(col["max_target_stall_room"]) == 21 && $(col["max_target_stall_frames"]) > 1800)
      stalled_sentinel = 1
  }
  END {
    if (rows != 1) { print "[sauran-frost-lane] missing deterministic row" > "/dev/stderr"; exit 1 }
    if (wrong_seed) { print "[sauran-frost-lane] fixed world drifted" > "/dev/stderr"; exit 1 }
    if (missed_frost || stalled_sentinel) {
      print "[sauran-frost-lane] covered Sentinel lane regressed" > "/dev/stderr"
      exit 1
    }
  }
' "$OUT"
echo "[sauran-frost-lane] PASS Tail Spike clears the covered Frost Sentinel"
