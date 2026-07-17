#!/usr/bin/env bash
# Regression: controller-only routing must path around cover to collect the
# non-magnetic Rift Sigil. The paired seed used to leave the agent pressing
# into a pillar in room 2 for its entire run.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ROM="${1:-$ROOT/rom/working/quintra.gbc}"
OUT="$(mktemp /tmp/quintra-rift-sigil-path.XXXXXX)"

QUINTRA_BALANCE_RUNS=2 QUINTRA_BALANCE_CLASSES=0 \
  QUINTRA_BALANCE_FRAMES=7000 QUINTRA_BALANCE_HOST_TIMEOUT=50 \
  QUINTRA_BALANCE_OUT="$OUT" \
  bash "$ROOT/scripts/run_balance_bot.sh" "$ROM" >/dev/null

max_room=$(awk -F, 'NR == 2 { print $5 }' "$OUT")
test "${max_room:-0}" -ge 6
echo "[rift-sigil-path] PASS room=$max_room"
