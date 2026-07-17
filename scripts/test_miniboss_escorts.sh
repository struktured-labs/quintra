#!/usr/bin/env bash
# Regression: fixed mini-boss escort coordinates must not overlap seeded crates.
# This uses only controller input through the real mGBA cartridge; before the
# safe-spawn fix, the seed below left room 3 sealed around a Flutterbat inside
# a crate and could not reach room 4.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ROM="${1:-$ROOT/rom/working/quintra.gbc}"
OUT="$(mktemp /tmp/quintra-miniboss-escort.XXXXXX)"

QUINTRA_BALANCE_RUNS=1 QUINTRA_BALANCE_CLASSES=0 \
  QUINTRA_BALANCE_FRAMES=3000 QUINTRA_BALANCE_HOST_TIMEOUT=40 \
  QUINTRA_BALANCE_OUT="$OUT" \
  bash "$ROOT/scripts/run_balance_bot.sh" "$ROM" >/dev/null

rooms_cleared=$(awk -F, 'NR == 2 { print $7 }' "$OUT")
max_room=$(awk -F, 'NR == 2 { print $5 }' "$OUT")
test "${rooms_cleared:-0}" -ge 4
test "${max_room:-0}" -ge 6
echo "[miniboss-escorts] PASS room=$max_room clears=$rooms_cleared"
