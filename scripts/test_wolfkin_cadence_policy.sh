#!/usr/bin/env bash
# Regression: the real-melee Wolfkin needs the two-beat giant pressure lane.
# These fixed title-frame replays cover three generated openings. The policy
# must reach every dedicated miniboss and clear a first giant on at least two
# paths; a bot-only route must not become a demand to soften human combat.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ROM="${1:-$ROOT/rom/working/quintra.gbc}"
OUT="$(mktemp /tmp/quintra-wolfkin-cadence.XXXXXX)"

for replay in '1 520 2064128323' '2 540 2064128343' '3 560 2064128379'; do
  read -r run frame seed <<EOF
$replay
EOF
  # Paired 224x200 wings make the input-only pilot's pixel-route search
  # materially heavier on seed three. Keep the exact 18,000 cartridge frames
  # and combat requirements; this is only a host-process watchdog.
  QUINTRA_BALANCE_RUNS="$run" QUINTRA_BALANCE_CLASSES=0 \
    QUINTRA_BALANCE_TARGET_FRAME="$frame" \
    QUINTRA_BALANCE_FRAMES=18000 QUINTRA_BALANCE_HOST_TIMEOUT=75 \
    QUINTRA_BALANCE_OUT="$OUT" QUINTRA_BALANCE_APPEND=1 \
    QUINTRA_BALANCE_SKIP_REPORT=1 \
    bash "$ROOT/scripts/run_balance_bot.sh" "$ROM" >/dev/null
done

awk -F, '
  NR == 1 {
    for (i = 1; i <= NF; ++i) col[$i] = i
    next
  }
  {
    rows++
    expected = (NR == 2 ? 2064128323 : NR == 3 ? 2064128343 : 2064128379)
    if ($(col["seed"]) != expected) wrong_seed = 1
    bosses += $(col["bosses"])
    if ($(col["bosses"]) >= 1) first_clears++
    if ($(col["max_room"]) < 3) missed_miniboss = 1
    if ($(col["death_source"]) != 255) deaths++
  }
  END {
    if (rows != 3) { print "[wolfkin-cadence] missing fixed rows" > "/dev/stderr"; exit 1 }
    if (wrong_seed) { print "[wolfkin-cadence] fixed world drifted" > "/dev/stderr"; exit 1 }
    if (missed_miniboss || first_clears < 2 || bosses < 2) {
      print "[wolfkin-cadence] fixed melee-route floor regressed" > "/dev/stderr"; exit 1
    }
    if (deaths > 3) { print "[wolfkin-cadence] unexpected extra deaths" > "/dev/stderr"; exit 1 }
  }
' "$OUT"
echo "[wolfkin-cadence] PASS fixed claw lane reached all minibosses and cleared two first giants"
