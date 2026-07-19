#!/usr/bin/env bash
# Compare real-input controller policies without changing ROM RAM. Defaults
# target the two classes whose boss geometry benefits most from a sweep;
# callers can additionally sweep the short-range lunge contact buffer or
# Sauran's real B-shield body-contact radius.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ROM="${1:-$ROOT/rom/working/quintra.gbc}"
CLASSES="${QUINTRA_POLICY_CLASSES:-1 2}"
POLICIES="${QUINTRA_POLICY_POLICIES:-baseline orbit orbit_fire pulse_fire}"
LUNGE_PANIC_RANGES="${QUINTRA_POLICY_LUNGE_PANIC_RANGES:-16}"
SAURAN_BODY_SHIELD_RANGES="${QUINTRA_POLICY_SAURAN_BODY_SHIELD_RANGES:-0}"
REPS="${QUINTRA_POLICY_REPS:-3}"
FRAMES="${QUINTRA_POLICY_FRAMES:-18000}"
TIMEOUT="${QUINTRA_POLICY_HOST_TIMEOUT:-45}"
OUTDIR="${QUINTRA_POLICY_OUTDIR:-$ROOT/tmp/policy-sweep}"

# Accept both shell-friendly and copy/paste-friendly forms. This remains an
# agent-only experiment: each candidate presses ordinary buttons against the
# same ROM and deterministic seed grid.
LUNGE_PANIC_RANGES="${LUNGE_PANIC_RANGES//,/ }"
SAURAN_BODY_SHIELD_RANGES="${SAURAN_BODY_SHIELD_RANGES//,/ }"

mkdir -p "$OUTDIR"
printf 'class,policy,lunge_panic_range,sauran_body_shield_range,runs,bosses,wins,max_room,min_hp,combat_stalls,route_stalls\n'

for class in $CLASSES; do
  for policy in $POLICIES; do
    for lunge_panic_range in $LUNGE_PANIC_RANGES; do
      for sauran_body_shield_range in $SAURAN_BODY_SHIELD_RANGES; do
    out="$OUTDIR/class-$class-$policy-lunge-$lunge_panic_range-shield-$sauran_body_shield_range.csv"
    # A candidate must never inherit a player save or another candidate's
    # suspended run. Keep mGBA battery RAM in a fresh caller-owned directory
    # so this remains a genuine matched-seed controller comparison.
    save_dir="$(mktemp -d "$OUTDIR/.save-$class-$policy-lunge-$lunge_panic_range-shield-$sauran_body_shield_range.XXXXXX")"
    QUINTRA_BOT_GIANT_POLICY="$policy" \
      QUINTRA_BOT_LUNGE_PANIC_RANGE="$lunge_panic_range" \
      QUINTRA_BOT_SAURAN_BODY_SHIELD_RANGE="$sauran_body_shield_range" \
      QUINTRA_BALANCE_REPS="$REPS" \
      QUINTRA_BALANCE_CLASSES="$class" \
      QUINTRA_BALANCE_FRAMES="$FRAMES" \
      QUINTRA_BALANCE_HOST_TIMEOUT="$TIMEOUT" \
      QUINTRA_BALANCE_OUT="$out" \
      QUINTRA_MGBA_SAVE_DIR="$save_dir" \
      QUINTRA_BALANCE_SKIP_REPORT=1 \
      bash "$ROOT/scripts/run_balance_bot.sh" "$ROM" >/dev/null
    awk -F, -v class="$class" -v policy="$policy" -v lunge="$lunge_panic_range" \
      -v shield="$sauran_body_shield_range" '
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
        if ($(col["max_target_stall_frames"]) > 3600 && $(col["min_hp"]) > 0) combat_stalls++
        if ($(col["max_route_frames"]) > 3600) route_stalls++
      }
      END {
        printf "%d,%s,%d,%d,%d,%d,%d,%d,%d,%d,%d\n", class, policy, lunge, shield,
          rows, bosses, wins, max_room, min_hp, combat_stalls, route_stalls
      }
    ' "$out"
      done
    done
  done
done
