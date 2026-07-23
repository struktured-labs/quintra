#!/usr/bin/env bash
# Regression: the controller-only balance pilot must collect the guaranteed
# post-colossus relics it uses to assess the game's real run-power curve.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ROM="${1:-$ROOT/rom/working/quintra.gbc}"
OUT="$(mktemp /tmp/quintra-boss-relics.XXXXXX)"

# Relic pickup behavior is the contract; multiple colossus wins are merely
# setup. Keep that setup deterministic with the coarse tester assist.
QUINTRA_BOT_EASY=1 QUINTRA_BALANCE_RUNS=1 QUINTRA_BALANCE_CLASSES=1 \
  QUINTRA_BALANCE_TARGET_FRAME=460 QUINTRA_BALANCE_FRAMES=18000 \
  QUINTRA_BALANCE_HOST_TIMEOUT=45 QUINTRA_BALANCE_OUT="$OUT" \
  QUINTRA_BALANCE_SKIP_REPORT=1 \
  bash "$ROOT/scripts/run_balance_bot.sh" "$ROM" >/dev/null

awk -F, '
  NR == 1 { for (i = 1; i <= NF; ++i) col[$i] = i; next }
  NR == 2 {
    if ($(col["seed"]) != 2064128647) exit 1
    if ($(col["bosses"]) < 2) exit 1
    if ($(col["boss_relics_seen"]) < 2) exit 1
    if ($(col["boss_relics_collected"]) != $(col["boss_relics_seen"])) exit 1
    if ($(col["boss_relics_missed"]) != 0) exit 1
    found = 1
  }
  END { if (!found) exit 1 }
' "$OUT"

echo "[boss-relics] PASS controller collected every observed post-boss relic"
