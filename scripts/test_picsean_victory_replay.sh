#!/usr/bin/env bash
# Full controller-only completion proof. The Picsean guard/town policy clears
# all nine bosses on this deterministic seed, then a fresh emulator replays
# the exact recorded buttons and must reproduce the victory outcome.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ROM="${1:-$ROOT/rom/working/quintra.gbc}"
NOI="${ROM%.gbc}.noi"
TMP="$(mktemp -d /tmp/quintra-picsean-victory.XXXXXX)"
CSV="$TMP/run.csv"
TRACE_DIR="$TMP/traces"
TRACE="$TRACE_DIR/run-13-class-3-1.trace"
RESULT="$TMP/replay.result"
MGBA_BIN="${QUINTRA_MGBA_BIN:-mgba-headless}"

RS=$(awk '/DEF _run_state / {print $3}' "$NOI")
PL=$(awk '/DEF _player / {print $3}' "$NOI")
EN=$(awk '/DEF _entities / {print $3}' "$NOI")
TM=$(awk '/DEF _room_tilemap / {print $3}' "$NOI")
LS=$(awk '/DEF _loop_current_screen / {print $3}' "$NOI")
FC=$(awk '/DEF _loop_frame_counter / {print $3}' "$NOI")

QUINTRA_BALANCE_RUNS=13 QUINTRA_BALANCE_CLASSES=3 \
  QUINTRA_BALANCE_FRAMES=90000 QUINTRA_BALANCE_HOST_TIMEOUT=120 \
  QUINTRA_BALANCE_TRACE_DIR="$TRACE_DIR" QUINTRA_BALANCE_OUT="$CSV" \
  bash "$ROOT/scripts/run_balance_bot.sh" "$ROM" >/dev/null

awk -F, '
  NR == 1 { for (i = 1; i <= NF; ++i) col[$i] = i; next }
  NR == 2 {
    if ($(col["victory"]) != 1 || $(col["bosses"]) != 9) {
      print "[picsean-victory] controller did not finish all nine bosses" > "/dev/stderr"
      exit 1
    }
    if ($(col["frames"]) > 90000) {
      print "[picsean-victory] frame budget exceeded" > "/dev/stderr"
      exit 1
    }
    found = 1
  }
  END { if (!found) exit 1 }
' "$CSV"
test -s "$TRACE"

env QUINTRA_RS_ADDR="$RS" QUINTRA_PL_ADDR="$PL" QUINTRA_EN_ADDR="$EN" \
  QUINTRA_TM_ADDR="$TM" QUINTRA_SCREEN_ADDR="$LS" QUINTRA_FRAME_ADDR="$FC" \
  QUINTRA_REPLAY_TRACE="$TRACE" QUINTRA_REPLAY_RESULT="$RESULT" \
  "$MGBA_BIN" "$ROM" --script "$ROOT/scripts/quintra_replay.lua" -l 0 \
  >/dev/null 2>&1 &
REPLAY_PID=$!
for _ in $(seq 1 480); do
  test -s "$RESULT" && break
  kill -0 "$REPLAY_PID" 2>/dev/null || break
  sleep 0.25
done
kill "$REPLAY_PID" 2>/dev/null || true
wait "$REPLAY_PID" 2>/dev/null || true
test -s "$RESULT"
grep -q '^PASS ' "$RESULT"
grep -q 'bosses=9' "$RESULT"
grep -q 'won=1' "$RESULT"
echo "[picsean-victory] $(cat "$RESULT")"
