#!/usr/bin/env bash
# Compare real-input giant-fight controller policies without changing ROM RAM.
# Defaults target the two classes whose boss geometry benefits most from a
# sweep; callers can widen the matrix through environment variables.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ROM="${1:-$ROOT/rom/working/quintra.gbc}"
CLASSES="${QUINTRA_POLICY_CLASSES:-1 2}"
POLICIES="${QUINTRA_POLICY_POLICIES:-baseline orbit orbit_fire pulse_fire}"
REPS="${QUINTRA_POLICY_REPS:-3}"
FRAMES="${QUINTRA_POLICY_FRAMES:-18000}"
TIMEOUT="${QUINTRA_POLICY_HOST_TIMEOUT:-45}"
OUTDIR="${QUINTRA_POLICY_OUTDIR:-$ROOT/tmp/policy-sweep}"

mkdir -p "$OUTDIR"
printf 'class,policy,runs,bosses,wins,max_room,min_hp,combat_stalls,route_stalls\n'

for class in $CLASSES; do
  for policy in $POLICIES; do
    out="$OUTDIR/class-$class-$policy.csv"
    QUINTRA_BOT_GIANT_POLICY="$policy" \
      QUINTRA_BALANCE_REPS="$REPS" \
      QUINTRA_BALANCE_CLASSES="$class" \
      QUINTRA_BALANCE_FRAMES="$FRAMES" \
      QUINTRA_BALANCE_HOST_TIMEOUT="$TIMEOUT" \
      QUINTRA_BALANCE_OUT="$out" \
      QUINTRA_BALANCE_SKIP_REPORT=1 \
      bash "$ROOT/scripts/run_balance_bot.sh" "$ROM" >/dev/null
    awk -F, -v class="$class" -v policy="$policy" '
      NR == 1 {
        for (i = 1; i <= NF; ++i) col[$i] = i
        next
      }
      {
        rows++
        bosses += $(col["bosses"])
        wins += $(col["victory"])
        if ($(col["max_room"]) > max_room) max_room = $(col["max_room"])
        if (rows == 1 || $(col["min_hp"]) < min_hp) min_hp = $(col["min_hp"])
        if ($(col["max_combat_frames"]) > 3600 && $(col["min_hp"]) > 0) combat_stalls++
        if ($(col["max_route_frames"]) > 3600) route_stalls++
      }
      END {
        printf "%d,%s,%d,%d,%d,%d,%d,%d,%d\n", class, policy, rows, bosses,
          wins, max_room, min_hp, combat_stalls, route_stalls
      }
    ' "$out"
  done
done
