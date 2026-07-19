#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ROM="${1:-$ROOT/rom/working/quintra.gbc}"
NOI="${ROM%.gbc}.noi"
TMP="$ROOT/tmp/replay-test"
mkdir -p "$TMP"
TRACE="$TMP/run.trace"
RESULT="$TMP/replay.result"
CSV="$TMP/run.csv"
MGBA_BIN="${QUINTRA_MGBA_BIN:-mgba-headless}"
RS=$(awk '/DEF _run_state / {print $3}' "$NOI")
PL=$(awk '/DEF _player / {print $3}' "$NOI")
EN=$(awk '/DEF _entities / {print $3}' "$NOI")
TM=$(awk '/DEF _room_tilemap / {print $3}' "$NOI")
LS=$(awk '/DEF _loop_current_screen / {print $3}' "$NOI")
FC=$(awk '/DEF _loop_frame_counter / {print $3}' "$NOI")
HEADER="run,class,seed,frames,max_room,rooms_seen,rooms_cleared,kills,bosses,damage,giant_overlap_damage,min_hp,final_x,final_y,world_mode,world_screen,room_frames,max_combat_frames,max_combat_room,max_combat_enemy,max_target_stall_frames,max_target_stall_room,max_target_stall_enemy,max_route_frames,max_route_room,hostiles,last_enemy,death_source,towns,world_hops,victory,ui_screen,dodges,shop_visits,purchases,enemy_mask,min_giant_hp,b_uses,boss_attempts,boss_attempt_frames,boss_clear_frames,town_market_visits,town_quarter_visits,boss_clear_durations"
echo "$HEADER" > "$CSV"
: > "$TRACE"
: > "$RESULT"
COMMON=(QUINTRA_RS_ADDR="$RS" QUINTRA_PL_ADDR="$PL" QUINTRA_EN_ADDR="$EN"
  QUINTRA_TM_ADDR="$TM" QUINTRA_SCREEN_ADDR="$LS" QUINTRA_FRAME_ADDR="$FC")
command -v "$MGBA_BIN" >/dev/null
env "${COMMON[@]}" \
  QUINTRA_BOT_RUN=1 QUINTRA_BOT_CLASS=2 QUINTRA_BOT_FRAMES=2400 \
  QUINTRA_MGBA_SAVE_DIR="$TMP/save" \
  QUINTRA_BOT_OUT="$CSV" QUINTRA_BOT_TRACE_OUT="$TRACE" \
  "$MGBA_BIN" -C "savegamePath=$TMP/save" "$ROM" \
  --script "$ROOT/scripts/quintra_balance_bot.lua" -l 0 >/dev/null 2>&1 &
AGENT_PID=$!
for _ in $(seq 1 180); do
  test "$(wc -l < "$CSV")" -gt 1 && break
  kill -0 "$AGENT_PID" 2>/dev/null || break
  sleep 0.25
done
kill "$AGENT_PID" 2>/dev/null || true
wait "$AGENT_PID" 2>/dev/null || true
test -s "$TRACE"
awk -F, 'NR == 1 { expected = NF; next } NR == 2 { exit NF == expected ? 0 : 1 } END { if (NR < 2) exit 1 }' "$CSV"
env "${COMMON[@]}" \
  QUINTRA_REPLAY_TRACE="$TRACE" QUINTRA_REPLAY_RESULT="$RESULT" \
  "$MGBA_BIN" -C "savegamePath=$TMP/replay-save" "$ROM" \
  --script "$ROOT/scripts/quintra_replay.lua" -l 0 >/dev/null 2>&1 &
REPLAY_PID=$!
for _ in $(seq 1 180); do
  test -s "$RESULT" && break
  kill -0 "$REPLAY_PID" 2>/dev/null || break
  sleep 0.25
done
kill "$REPLAY_PID" 2>/dev/null || true
wait "$REPLAY_PID" 2>/dev/null || true
test -s "$RESULT"
grep -q '^PASS ' "$RESULT"
transitions=$(grep -vc '^#' "$TRACE")
frames=$(sed -n 's/^# outcome .* frames=\([0-9][0-9]*\)$/\1/p' "$TRACE")
test "$transitions" -lt "$frames"
echo "[replay] $(cat "$RESULT") transitions=$transitions"
