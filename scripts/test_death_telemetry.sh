#!/usr/bin/env bash
# Regression: balance telemetry must preserve a fatal-event context without
# touching cartridge RAM. The selected fixed-frame Sauran world currently
# dies during a giant encounter; if a future balance change lets it live, the
# sentinel values still prove the schema stays internally consistent.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ROM="${1:-$ROOT/rom/working/quintra.gbc}"
OUT="$(mktemp /tmp/quintra-death-telemetry.XXXXXX)"
trap 'rm -f "$OUT" "$OUT.lock"' EXIT

QUINTRA_BALANCE_RUNS=3 QUINTRA_BALANCE_CLASSES=1 \
  QUINTRA_BALANCE_REPS=1 QUINTRA_BALANCE_TARGET_FRAME=420 \
  QUINTRA_BALANCE_FRAMES=12000 QUINTRA_BALANCE_HOST_TIMEOUT=120 \
  QUINTRA_BALANCE_OUT="$OUT" QUINTRA_BALANCE_SKIP_REPORT=1 \
  bash "$ROOT/scripts/run_balance_bot.sh" "$ROM" >/dev/null

awk -F, '
  NR == 1 {
    for (i = 1; i <= NF; ++i) col[$i] = i
    if (!(("death_source" in col) && ("death_room" in col) && ("death_bosses" in col) && ("death_giant" in col) && ("death_giant_overlap" in col))) exit 1
    next
  }
  NR == 2 {
    rows++
    if ($(col["min_hp"]) == 0) {
      if ($(col["death_room"]) == 255) bad = 1
      if ($(col["death_bosses"]) > $(col["bosses"])) bad = 1
      if ($(col["death_giant"]) != 0 && $(col["death_giant"]) != 1) bad = 1
      if ($(col["death_giant_overlap"]) != 0 && $(col["death_giant_overlap"]) != 1) bad = 1
      if ($(col["death_giant_overlap"]) > $(col["death_giant"])) bad = 1
      if ($(col["death_source"]) == 255) bad = 1
    } else if ($(col["death_source"]) != 255 || $(col["death_room"]) != 255 || $(col["death_bosses"]) != 0 || $(col["death_giant"]) != 0 || $(col["death_giant_overlap"]) != 0) {
      bad = 1
    }
  }
  END { exit (rows == 1 && !bad) ? 0 : 1 }
' "$OUT"

echo "[death-telemetry] PASS fatal source/room/boss/giant/body context is internally consistent"
