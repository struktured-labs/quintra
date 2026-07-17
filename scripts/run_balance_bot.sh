#!/usr/bin/env bash
# Run five honest controller-only agents against the built ROM.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ROM="${1:-$ROOT/rom/working/quintra.gbc}"
OUT="${QUINTRA_BALANCE_OUT:-$ROOT/tmp/balance-runs.csv}"
FRAMES="${QUINTRA_BALANCE_FRAMES:-10800}"
REPS="${QUINTRA_BALANCE_REPS:-3}"
MIN_WINS="${QUINTRA_BALANCE_MIN_WINS:-0}"
MIN_SHOP_RUNS="${QUINTRA_BALANCE_MIN_SHOP_RUNS:-0}"
STALL_FRAMES="${QUINTRA_BALANCE_STALL_FRAMES:-3600}"
MAX_COMBAT_STALLS="${QUINTRA_BALANCE_MAX_COMBAT_STALLS:-}"
MAX_ROUTE_STALLS="${QUINTRA_BALANCE_MAX_ROUTE_STALLS:-}"
MAX_WORLD_HOPS="${QUINTRA_BALANCE_MAX_WORLD_HOPS:-}"
REQUIRED_ENEMIES="${QUINTRA_BALANCE_REQUIRED_ENEMIES:-}"
HOST_TIMEOUT="${QUINTRA_BALANCE_HOST_TIMEOUT:-180}"
TRACE_DIR="${QUINTRA_BALANCE_TRACE_DIR:-}"
APPEND="${QUINTRA_BALANCE_APPEND:-0}"
SKIP_REPORT="${QUINTRA_BALANCE_SKIP_REPORT:-0}"
read -r -a CLASS_IDS <<< "${QUINTRA_BALANCE_CLASSES:-0 1 2 3 4}"
if [ -n "${QUINTRA_BALANCE_RUNS:-}" ]; then
  read -r -a RUN_IDS <<< "$QUINTRA_BALANCE_RUNS"
else
  mapfile -t RUN_IDS < <(seq 1 "$REPS")
fi
NOI="${ROM%.gbc}.noi"

RS=$(awk '/DEF _run_state / {print $3}' "$NOI")
PL=$(awk '/DEF _player / {print $3}' "$NOI")
EN=$(awk '/DEF _entities / {print $3}' "$NOI")
TM=$(awk '/DEF _room_tilemap / {print $3}' "$NOI")
LS=$(awk '/DEF _loop_current_screen / {print $3}' "$NOI")
FC=$(awk '/DEF _loop_frame_counter / {print $3}' "$NOI")
mkdir -p "$(dirname "$OUT")"
if [ -n "$TRACE_DIR" ]; then mkdir -p "$TRACE_DIR"; fi
if [ "$APPEND" != 1 ] || [ ! -s "$OUT" ]; then
  echo "run,class,seed,frames,max_room,rooms_seen,rooms_cleared,kills,bosses,damage,min_hp,final_x,final_y,world_mode,world_screen,room_frames,max_combat_frames,max_combat_room,max_combat_enemy,max_route_frames,max_route_room,hostiles,last_enemy,death_source,towns,world_hops,victory,ui_screen,dodges,shop_visits,purchases,enemy_mask" > "$OUT"
fi

unset DISPLAY WAYLAND_DISPLAY
for run in "${RUN_IDS[@]}"; do
  for class in "${CLASS_IDS[@]}"; do
    echo "[balance] run $run/$REPS class $class"
    completed=false
    # mGBA occasionally drops the Lua process before its final CSV append.
    # Retry just that controller-only trial once; a matrix is never silently
    # reported with a missing class/seed row.
    for attempt in 1 2; do
      before=$(wc -l < "$OUT")
      log="/tmp/quintra-balance-$run-$class-$attempt.log"
      trace_env=()
      if [ -n "$TRACE_DIR" ]; then
        trace_env+=("QUINTRA_BOT_TRACE_OUT=$TRACE_DIR/run-$run-class-$class-$attempt.trace")
      fi
      env "${trace_env[@]}" QT_QPA_PLATFORM=offscreen SDL_AUDIODRIVER=dummy \
        QUINTRA_RS_ADDR="$RS" QUINTRA_PL_ADDR="$PL" QUINTRA_EN_ADDR="$EN" QUINTRA_TM_ADDR="$TM" \
        QUINTRA_SCREEN_ADDR="$LS" \
        QUINTRA_FRAME_ADDR="$FC" \
        QUINTRA_BOT_RUN="$run" QUINTRA_BOT_CLASS="$class" \
        QUINTRA_BOT_FRAMES="$FRAMES" QUINTRA_BOT_OUT="$OUT" \
        setsid timeout "$HOST_TIMEOUT" xvfb-run -a mgba-qt "$ROM" --fastforward --script "$ROOT/scripts/quintra_balance_bot.lua" -l 0 \
        >"$log" 2>&1 &
      pid=$!
      # This mGBA build does not honor frontend:quit from Lua reliably. The
      # completed CSV row is the transaction boundary; stop the wrapper then.
      for _ in $(seq 1 $((HOST_TIMEOUT * 4))); do
          now=$(wc -l < "$OUT")
          if [ "$now" -gt "$before" ]; then break; fi
          if ! kill -0 "$pid" 2>/dev/null; then break; fi
          sleep 0.25
      done
      # Each trial owns its Xvfb/mGBA process group. Never use a global pkill:
      # it races other class trials and used to truncate parallel matrices.
      kill -- -"$pid" 2>/dev/null || true
      wait "$pid" 2>/dev/null || true
      grep 'BALANCE' "$log" || true
      if [ "$now" -gt "$before" ]; then
        completed=true
        break
      fi
      echo "[balance] missing CSV row; retrying run $run class $class (attempt $attempt/2)" >&2
    done
    if [ "$completed" != true ]; then
      echo "[balance] ERROR no CSV row for run $run class $class after retry" >&2
      exit 1
    fi
  done
done
if [ "$SKIP_REPORT" = 1 ]; then
  echo "[balance] batch recorded: $OUT"
  exit 0
fi
REPORT_ARGS=(report "$OUT" --runs "${#RUN_IDS[@]}" --classes "${#CLASS_IDS[@]}" \
  --min-wins "$MIN_WINS" --min-shop-runs "$MIN_SHOP_RUNS" \
  --stall-frames "$STALL_FRAMES")
if [ -n "$MAX_COMBAT_STALLS" ]; then
  REPORT_ARGS+=(--max-combat-stalls "$MAX_COMBAT_STALLS")
fi
if [ -n "$MAX_ROUTE_STALLS" ]; then
  REPORT_ARGS+=(--max-route-stalls "$MAX_ROUTE_STALLS")
fi
if [ -n "$MAX_WORLD_HOPS" ]; then
  REPORT_ARGS+=(--max-world-hops "$MAX_WORLD_HOPS")
fi
if [ -n "$REQUIRED_ENEMIES" ]; then
  for enemy in $REQUIRED_ENEMIES; do REPORT_ARGS+=(--require-enemy "$enemy"); done
fi
cargo run --quiet --manifest-path "$ROOT/Cargo.toml" -p quintra-mgba -- \
  "${REPORT_ARGS[@]}"
