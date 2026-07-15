#!/usr/bin/env bash
# Run five honest controller-only agents against the built ROM.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ROM="${1:-$ROOT/rom/working/quintra.gbc}"
OUT="${QUINTRA_BALANCE_OUT:-$ROOT/tmp/balance-runs.csv}"
FRAMES="${QUINTRA_BALANCE_FRAMES:-10800}"
REPS="${QUINTRA_BALANCE_REPS:-3}"
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
echo "run,class,seed,frames,max_room,rooms_seen,rooms_cleared,kills,bosses,damage,min_hp,final_x,final_y,world_mode,world_screen,room_frames,hostiles,last_enemy,towns,world_hops,victory,ui_screen" > "$OUT"

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
      timeout 90 xvfb-run -a mgba-qt "$ROM" --fastforward --script "$ROOT/scripts/quintra_balance_bot.lua" -l 0 \
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
    kill "$pid" 2>/dev/null || true
    wait "$pid" 2>/dev/null || true
    grep 'BALANCE' "$log" || true
  done
done
pkill -9 -f 'Xvfb :' 2>/dev/null || true

python3 - "$OUT" "${#RUN_IDS[@]}" "${#CLASS_IDS[@]}" <<'PY'
import csv, statistics, sys
rows = list(csv.DictReader(open(sys.argv[1])))
expected = int(sys.argv[2]) * int(sys.argv[3])
print(f"[balance] {len(rows)}/{expected} agents reported")
names = ["Wolfkin", "Sauran", "Corvin", "Picsean", "Vespine"]
for cls, name in enumerate(names):
    sample = [r for r in rows if int(r['class']) == cls]
    if not sample: continue
    rooms = [int(r['max_room']) for r in sample]
    clears = [int(r['rooms_cleared']) for r in sample]
    kills = [int(r['kills']) for r in sample]
    bosses = [int(r['bosses']) for r in sample]
    towns = [int(r['towns']) for r in sample]
    deaths = sum(int(r['min_hp']) == 0 for r in sample)
    wins = sum(int(r['victory']) != 0 for r in sample)
    endings = sum(int(r['victory']) != 0 and int(r['ui_screen']) == 12 for r in sample)
    boss_clears = sum(b > 0 for b in bosses)
    combat_stalls = sum(int(r['room_frames']) > 3600 and int(r['hostiles']) > 0 for r in sample)
    route_stalls = sum(int(r['room_frames']) > 3600 and int(r['hostiles']) == 0
                       and int(r['victory']) == 0 for r in sample)
    print(f"[balance] {name:7s} n={len(sample)} room_med={statistics.median(rooms):g} "
          f"clear_med={statistics.median(clears):g} kill_med={statistics.median(kills):g} "
          f"boss_med={statistics.median(bosses):g} boss1={boss_clears}/{len(sample)} "
          f"town_med={statistics.median(towns):g} wins={wins} endings={endings} "
          f"deaths={deaths} combat_stalls={combat_stalls} route_stalls={route_stalls}")
if len(rows) != expected:
    raise SystemExit(1)
PY
echo "[balance] raw data: $OUT"
