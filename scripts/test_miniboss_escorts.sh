#!/usr/bin/env bash
# Regression: fixed mini-boss escort coordinates must not overlap seeded crates.
# This uses only controller input through the real mGBA cartridge; before the
# safe-spawn fix, the seed below left room 3 sealed around a Flutterbat inside
# a crate and could not reach room 4.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ROM="${1:-$ROOT/rom/working/quintra.gbc}"
OUT="$(mktemp /tmp/quintra-miniboss-escort.XXXXXX)"

# Room slides, the Sigil detour, and a real shop purchase all consume
# controller time before the boss threshold. This is still a short escort-path
# regression window, but 3000 frames cuts off a healthy run immediately before
# room 6 on the current cartridge pacing.
QUINTRA_BALANCE_RUNS=1 QUINTRA_BALANCE_CLASSES=0 \
  QUINTRA_BALANCE_FRAMES=3600 QUINTRA_BALANCE_HOST_TIMEOUT=40 \
  QUINTRA_BALANCE_OUT="$OUT" \
  bash "$ROOT/scripts/run_balance_bot.sh" "$ROM" >/dev/null

rooms_cleared=$(awk -F, 'NR == 2 { print $7 }' "$OUT")
max_room=$(awk -F, 'NR == 2 { print $5 }' "$OUT")
# The run-state counter records only cleared combat rooms. The sanctuary at
# room 5 and the boss entry are intentionally not combat clears, so reaching
# room 6 after the room-3 escort means exactly three early combat clears.
test "${rooms_cleared:-0}" -ge 3
test "${max_room:-0}" -ge 6
echo "[miniboss-escorts] PASS escort route reached room=$max_room clears=$rooms_cleared"
