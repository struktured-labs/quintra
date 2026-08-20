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
# controller time before the boss threshold. The continuous 31x31 opening
# fields now make the same honest route materially longer than the old compact
# rooms: 4,400 frames expires inside room 3 and 60 host seconds expires before
# mGBA can publish its CSV row. Preserve the controller-only proof with the
# measured current route/host budgets.
# Vespine's ranged fan reliably completes this dense seed and reaches its
# generated Warden in the fixed budget. Wolfkin now spends that same window
# learning the optional room-10 melee crowd rather than reaching the fixture,
# which made the old class choice a combat-balance test instead of an escort
# placement test.
QUINTRA_BALANCE_RUNS=1 QUINTRA_BALANCE_CLASSES=4 \
  QUINTRA_BALANCE_FRAMES=8000 QUINTRA_BALANCE_HOST_TIMEOUT=180 \
  QUINTRA_BALANCE_OUT="$OUT" \
  bash "$ROOT/scripts/run_balance_bot.sh" "$ROM" >/dev/null

rooms_cleared=$(awk -F, 'NR == 2 { print $7 }' "$OUT")
max_room=$(awk -F, 'NR == 2 { print $5 }' "$OUT")
# The seeded nonlinear route reaches the Sigil at cell 12, then doubles back
# through its generated Warden. Seeing the numeric high-water mark at 12 plus
# a real clear proves the controller survived that mandatory encounter; the
# live reachability test immediately after this one checks every authored
# Sentinel/escort position directly.
test "${rooms_cleared:-0}" -ge 1
test "${max_room:-0}" -ge 12
echo "[miniboss-escorts] PASS escort route reached room=$max_room clears=$rooms_cleared"
