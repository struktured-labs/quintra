#!/usr/bin/env bash
# Regression: a close-range champion hit by a giant in the top danger strip
# must not begin its eight-frame recovery dash upward into that wall. The fixed
# world reaches that live geometry using only title timing and ordinary
# controller inputs; debug output is read-only telemetry.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ROM="${1:-$ROOT/rom/working/quintra.gbc}"
DIR="$(mktemp -d /tmp/quintra-giant-wall-dash.XXXXXX)"
OUT="$DIR/balance.csv"

QUINTRA_BALANCE_RUNS=95 QUINTRA_BALANCE_CLASSES=0 \
  QUINTRA_BALANCE_TARGET_FRAME=460 QUINTRA_BALANCE_FRAMES=9000 \
  QUINTRA_BALANCE_HOST_TIMEOUT=45 QUINTRA_BALANCE_OUT="$OUT" \
  QUINTRA_BALANCE_DEBUG=1 QUINTRA_BALANCE_DEBUG_DIR="$DIR" \
  QUINTRA_BALANCE_SKIP_REPORT=1 \
  bash "$ROOT/scripts/run_balance_bot.sh" "$ROM" >/dev/null

LOG="$(find "$DIR" -name '*.log' -type f -print -quit)"
test -n "$LOG"
python3 - "$LOG" <<'PY'
import re
import sys

dash = re.compile(
    r"BOTBODYDASH f=(\d+) room=(\d+) pos=(\d+),(\d+) "
    r"target=(\d+)@(\d+),(\d+) dir=([0-9A-F]+)"
)
hit = re.compile(
    r"BOTHIT f=(\d+) room=(\d+) world=0:\d+ hp=\d+->\d+ "
    r"src=(\d+) pos=(\d+),(\d+)"
)
edge_dashes = 0
edge_hits = 0
for line in open(sys.argv[1], encoding="utf-8", errors="replace"):
    found_hit = hit.search(line)
    if found_hit:
        _frame, room, kind, _px, py = found_hit.groups()
        if int(kind) == 1 and int(py) <= 7:
            edge_hits += 1
    found = dash.search(line)
    if not found:
        continue
    _frame, room, _px, py, kind, _tx, ty, direction = found.groups()
    # Giant stage bosses are kind 1 in local room zero. The recovery itself is
    # eight pixels: y<=7 would cross the screen boundary, while y=8+ has a
    # legal full lane. Keep the assertion on the exact illegal strip. 0x40 is
    # UP.
    if int(kind) == 1 and int(py) <= 7:
        edge_dashes += 1
        if int(direction, 16) == 0x40:
            raise SystemExit("[giant-wall-dash] selected UP into the top wall")
if edge_hits == 0 and edge_dashes == 0:
    raise SystemExit("[giant-wall-dash] fixture did not reach a giant top-wall hit")
PY

echo "[giant-wall-dash] PASS giant recovery avoids a top-wall dash"
