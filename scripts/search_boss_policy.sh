#!/usr/bin/env bash
# Compare controller-only giant policies on the same real-ROM seed/class grid.
# Candidate modes never write RAM: the Lua agent only presses buttons.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ROM="${1:-$ROOT/rom/working/quintra.gbc}"
OUT_DIR="${QUINTRA_BOSS_SEARCH_OUT:-$ROOT/tmp/boss-policy-search}"
MODES="${QUINTRA_BOSS_SEARCH_MODES:-baseline orbit orbit_fire}"
RUNS="${QUINTRA_BOSS_SEARCH_RUNS:-1}"
CLASSES="${QUINTRA_BOSS_SEARCH_CLASSES:-1}"
FRAMES="${QUINTRA_BOSS_SEARCH_FRAMES:-18000}"
mkdir -p "$OUT_DIR"

printf 'mode rows boss_clears deaths min_giant_hp total_player_damage\n'
for mode in $MODES; do
  csv="$OUT_DIR/$mode.csv"
  # A controller trial may outlive an interrupted parent shell for a moment.
  # Give every candidate an unguessable output path so a late write from an
  # abandoned experiment can never contaminate this comparison.
  trial_csv="$(mktemp "$OUT_DIR/.boss-policy-${mode}.XXXXXX.csv")"
  QUINTRA_BOT_GIANT_POLICY="$mode" \
    QUINTRA_BALANCE_RUNS="$RUNS" QUINTRA_BALANCE_CLASSES="$CLASSES" \
    QUINTRA_BALANCE_FRAMES="$FRAMES" QUINTRA_BALANCE_OUT="$trial_csv" \
    bash "$ROOT/scripts/run_balance_bot.sh" "$ROM" >/dev/null
  awk -F, -v mode="$mode" '
    NR == 1 { for (i = 1; i <= NF; ++i) column[$i] = i; next }
    {
      rows++; bosses += $(column["bosses"]); damage += $(column["damage"])
      if ($(column["min_hp"]) == 0) deaths++
      giant = $(column["min_giant_hp"])
      if (giant < lowest) lowest = giant
    }
    END {
      if (lowest == 255) lowest = "-"
      printf "%s %d %d %d %s %d\n", mode, rows, bosses, deaths, lowest, damage
    }
  ' lowest=255 "$trial_csv"
  mv "$trial_csv" "$csv"
done
