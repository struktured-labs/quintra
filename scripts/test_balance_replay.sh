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
RS=$(awk '/DEF _run_state / {print $3}' "$NOI")
PL=$(awk '/DEF _player / {print $3}' "$NOI")
EN=$(awk '/DEF _entities / {print $3}' "$NOI")
TM=$(awk '/DEF _room_tilemap / {print $3}' "$NOI")
LS=$(awk '/DEF _loop_current_screen / {print $3}' "$NOI")
FC=$(awk '/DEF _loop_frame_counter / {print $3}' "$NOI")
HEADER="run,class,seed,frames,max_room,rooms_seen,rooms_cleared,kills,bosses,damage,min_hp,final_x,final_y,world_mode,world_screen,room_frames,max_combat_frames,max_combat_room,max_combat_enemy,max_route_frames,max_route_room,hostiles,last_enemy,death_source,towns,world_hops,victory,ui_screen,dodges,shop_visits,purchases,enemy_mask"
echo "$HEADER" > "$CSV"
COMMON=(QUINTRA_RS_ADDR="$RS" QUINTRA_PL_ADDR="$PL" QUINTRA_EN_ADDR="$EN"
  QUINTRA_TM_ADDR="$TM" QUINTRA_SCREEN_ADDR="$LS" QUINTRA_FRAME_ADDR="$FC")
unset DISPLAY WAYLAND_DISPLAY
env "${COMMON[@]}" QT_QPA_PLATFORM=offscreen SDL_AUDIODRIVER=dummy \
  QUINTRA_BOT_RUN=1 QUINTRA_BOT_CLASS=2 QUINTRA_BOT_FRAMES=2400 \
  QUINTRA_BOT_OUT="$CSV" QUINTRA_BOT_TRACE_OUT="$TRACE" \
  timeout 45 xvfb-run -a mgba-qt "$ROM" --fastforward \
  --script "$ROOT/scripts/quintra_balance_bot.lua" -l 0 >/dev/null 2>&1 || true
test -s "$TRACE"
env "${COMMON[@]}" QT_QPA_PLATFORM=offscreen SDL_AUDIODRIVER=dummy \
  QUINTRA_REPLAY_TRACE="$TRACE" QUINTRA_REPLAY_RESULT="$RESULT" \
  timeout 45 xvfb-run -a mgba-qt "$ROM" --fastforward \
  --script "$ROOT/scripts/quintra_replay.lua" -l 0 >/dev/null 2>&1 || true
test -s "$RESULT"
grep -q '^PASS ' "$RESULT"
transitions=$(grep -vc '^#' "$TRACE")
frames=$(sed -n 's/^# outcome .* frames=\([0-9][0-9]*\)$/\1/p' "$TRACE")
test "$transitions" -lt "$frames"
echo "[replay] $(cat "$RESULT") transitions=$transitions"
