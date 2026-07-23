#!/usr/bin/env bash
# Long-route regression: this fixed run-three world eventually presents a
# Skeleton in Sauran's right-hand sprite strip with a valid vertical Tail
# Spike lane. The former inward-edge guard replaced every thrust with LEFT and
# stalled in room 31. Reaching that lane requires surviving the preceding
# bosses, so this remains a deliberately strict end-to-end survival check;
# it must not be presented as an isolated Skeleton fixture when an earlier
# loss occurs. Pinning the cartridge loop frame matters: a run number alone
# intentionally samples title-idle entropy and is not a regression replay.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ROM="${1:-$ROOT/rom/working/quintra.gbc}"
OUT="$(mktemp /tmp/quintra-sauran-edge.XXXXXX)"
trap 'rm -f "$OUT" "$OUT.lock"' EXIT

QUINTRA_BALANCE_RUNS=3 QUINTRA_BALANCE_CLASSES=1 \
  QUINTRA_BALANCE_REPS=1 QUINTRA_BALANCE_TARGET_FRAME=480 \
  QUINTRA_BALANCE_FRAMES=60000 \
  QUINTRA_BALANCE_HOST_TIMEOUT=90 QUINTRA_BALANCE_OUT="$OUT" \
  QUINTRA_BALANCE_SKIP_REPORT=1 \
  bash "$ROOT/scripts/run_balance_bot.sh" "$ROM" >/dev/null

awk -F, '
  NR == 1 {
    for (i = 1; i <= NF; ++i) col[$i] = i
    next
  }
  {
    rows++
    if ($(col["seed"]) != 2064128683) wrong_seed = 1
    bosses = $(col["bosses"])
    combat_room = $(col["max_combat_room"])
  }
  END {
    if (rows != 1) { print "[sauran-edge] missing deterministic row" > "/dev/stderr"; exit 1 }
    if (wrong_seed) { print "[sauran-edge] fixed controller world drifted" > "/dev/stderr"; exit 1 }
    if (bosses < 7) { print "[sauran-edge] did not survive to the right-edge Skeleton lane" > "/dev/stderr"; exit 1 }
    if (combat_room == 31) { print "[sauran-edge] still stalled in room 31" > "/dev/stderr"; exit 1 }
  }
' "$OUT"
echo "[sauran-edge] PASS Tail Spike escapes the right-edge Skeleton lane"
