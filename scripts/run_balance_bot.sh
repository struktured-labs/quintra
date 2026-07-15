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
mkdir -p "$(dirname "$OUT")"
echo "run,class,seed,frames,max_room,rooms_seen,rooms_cleared,kills,bosses,damage,min_hp,final_x,final_y,world_mode,world_screen,room_frames,max_combat_frames,max_combat_room,max_combat_enemy,max_route_frames,max_route_room,hostiles,last_enemy,towns,world_hops,victory,ui_screen,dodges,purchases" > "$OUT"

unset DISPLAY WAYLAND_DISPLAY
for run in "${RUN_IDS[@]}"; do
  for class in "${CLASS_IDS[@]}"; do
    echo "[balance] run $run/$REPS class $class"
    before=$(wc -l < "$OUT")
    log="/tmp/quintra-balance-$run-$class.log"
    QT_QPA_PLATFORM=offscreen SDL_AUDIODRIVER=dummy \
      QUINTRA_RS_ADDR="$RS" QUINTRA_PL_ADDR="$PL" QUINTRA_EN_ADDR="$EN" QUINTRA_TM_ADDR="$TM" \
      QUINTRA_SCREEN_ADDR="$LS" \
      QUINTRA_BOT_RUN="$run" QUINTRA_BOT_CLASS="$class" \
      QUINTRA_BOT_FRAMES="$FRAMES" QUINTRA_BOT_OUT="$OUT" \
      setsid timeout 90 xvfb-run -a mgba-qt "$ROM" --fastforward --script "$ROOT/scripts/quintra_balance_bot.lua" -l 0 \
      >"$log" 2>&1 &
    pid=$!
    # This mGBA build does not honor frontend:quit from Lua reliably. The
    # completed CSV row is the transaction boundary; stop the wrapper then.
    for _ in $(seq 1 360); do
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
  done
done
REPORT_ARGS=(report "$OUT" --runs "${#RUN_IDS[@]}" --classes "${#CLASS_IDS[@]}" \
  --min-wins "$MIN_WINS" --min-shop-runs "$MIN_SHOP_RUNS" \
  --stall-frames "$STALL_FRAMES")
if [ -n "$MAX_COMBAT_STALLS" ]; then
  REPORT_ARGS+=(--max-combat-stalls "$MAX_COMBAT_STALLS")
fi
if [ -n "$MAX_ROUTE_STALLS" ]; then
  REPORT_ARGS+=(--max-route-stalls "$MAX_ROUTE_STALLS")
fi
cargo run --quiet --manifest-path "$ROOT/Cargo.toml" -p quintra-mgba -- \
  "${REPORT_ARGS[@]}"
