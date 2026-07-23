#!/usr/bin/env bash
# Controller regression for the exact three pre-boss failures exposed by the
# Crystal-Colossus Normal matrix. This changes no cartridge state or balance:
# it proves the pilot can leave optional opening combat, survive the paired
# Rope route, and keep attacking a required 32x32 Sentinel at the north edge.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ROM="${1:-$ROOT/rom/working/quintra.gbc}"
VESPINE="$(mktemp /tmp/quintra-early-vespine.XXXXXX)"
ROOM3="$(mktemp /tmp/quintra-early-room3.XXXXXX)"
trap 'rm -f "$VESPINE" "$VESPINE.lock" "$ROOM3" "$ROOM3.lock"' EXIT

QUINTRA_BALANCE_OUT="$VESPINE" QUINTRA_BALANCE_RUNS="1 3" \
  QUINTRA_BALANCE_CLASSES=4 QUINTRA_BALANCE_FRAMES=12000 \
  QUINTRA_BALANCE_SKIP_REPORT=1 \
  bash "$ROOT/scripts/run_balance_bot.sh" "$ROM" >/dev/null

QUINTRA_BALANCE_OUT="$ROOM3" QUINTRA_BALANCE_RUNS=3 \
  QUINTRA_BALANCE_CLASSES="1 2" QUINTRA_BALANCE_FRAMES=12000 \
  QUINTRA_BALANCE_SKIP_REPORT=1 \
  bash "$ROOT/scripts/run_balance_bot.sh" "$ROM" >/dev/null

python3 - "$VESPINE" "$ROOM3" <<'PY'
import csv
import sys

vespine = list(csv.DictReader(open(sys.argv[1])))
room3 = list(csv.DictReader(open(sys.argv[2])))
assert len(vespine) == 2 and {int(row["run"]) for row in vespine} == {1, 3}
assert all(int(row["class"]) == 4 for row in vespine)
run1 = next(row for row in vespine if int(row["run"]) == 1)
run3 = next(row for row in vespine if int(row["run"]) == 3)
assert int(run1["max_room"]) >= 3, (
    "Vespine did not preserve enough health to reach the required Sentinel")
assert int(run3["bosses"]) >= 1, (
    "Vespine did not survive the paired opening Rope route to the Colossus")

assert len(room3) == 2 and {int(row["class"]) for row in room3} == {1, 2}
for row in room3:
    assert int(row["max_room"]) >= 6 and int(row["boss_attempts"]) >= 1, (
        f"class {row['class']} remained pinned in the required room-three "
        "Sentinel encounter")
assert next(int(row["bosses"]) for row in room3 if int(row["class"]) == 2) >= 1, (
    "Corvin did not clear the first Colossus after escaping the Sentinel edge")
PY

echo "[early-normal-policy] PASS Vespine preserves the opening/Rope routes; Sauran/Corvin clear room-three Sentinel"
