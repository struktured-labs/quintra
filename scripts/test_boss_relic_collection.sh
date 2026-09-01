#!/usr/bin/env bash
# Regression: the controller-only balance pilot must collect the guaranteed
# post-colossus relics it uses to assess the game's real run-power curve.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ROM="${1:-$ROOT/rom/working/quintra.gbc}"
OUT="$(mktemp /tmp/quintra-boss-relics.XXXXXX)"
STATE="$ROOT/tmp/mgba-states-smoke/quintra-stage-01-boss-picsean-easy.ss0"
test -s "$STATE"

# Relic pickup behavior is the contract; a Colossus win is merely setup.
# Campaign-wide repeated collection belongs to the nine-boss victory replay,
# which requires six physical collections and explicitly accounts for at most
# two far-side misses now that Road Echo combat support is an optional secret.
QUINTRA_MGBA_STATE="$STATE" QUINTRA_BALANCE_RESUME_STATE=1 \
  QUINTRA_BOT_EASY=1 QUINTRA_BALANCE_RUNS=1 QUINTRA_BALANCE_CLASSES=3 \
  QUINTRA_BALANCE_FRAMES=3000 \
  QUINTRA_BALANCE_HOST_TIMEOUT=1200 QUINTRA_BALANCE_OUT="$OUT" \
  QUINTRA_BALANCE_SKIP_REPORT=1 \
  bash "$ROOT/scripts/run_balance_bot.sh" "$ROM" >/dev/null

awk -F, '
  NR == 1 { for (i = 1; i <= NF; ++i) col[$i] = i; next }
  NR == 2 {
    if ($(col["bosses"]) < 1) exit 1
    if ($(col["boss_relics_seen"]) < 1) exit 1
    if ($(col["boss_relics_collected"]) != $(col["boss_relics_seen"])) exit 1
    if ($(col["boss_relics_missed"]) != 0) exit 1
    found = 1
  }
  END { if (!found) exit 1 }
' "$OUT"

echo "[boss-relics] PASS controller collected the observed post-boss relic"
