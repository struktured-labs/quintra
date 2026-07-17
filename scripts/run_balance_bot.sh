#!/usr/bin/env bash
# Run five honest controller-only agents against the built ROM.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ROM="${1:-$ROOT/rom/working/quintra.gbc}"
OUT="${QUINTRA_BALANCE_OUT:-$ROOT/tmp/balance-runs.csv}"
TRIAL_DIR="${QUINTRA_BALANCE_TRIAL_DIR:-$(dirname "$OUT")/balance-trials}"
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
MGBA_BIN="${QUINTRA_MGBA_BIN:-mgba-headless}"
# GBC cartridges are battery-backed. Test agents must not share the ROM's
# adjacent .sav file (or a player's manual save) when several mGBA processes
# run at once. Point mGBA at a caller-owned directory when requested.
MGBA_SAVE_DIR="${QUINTRA_MGBA_SAVE_DIR:-}"
MGBA_SAVE_ARGS=()
if [ -n "$MGBA_SAVE_DIR" ]; then
  mkdir -p "$MGBA_SAVE_DIR"
  MGBA_SAVE_ARGS=(-C "savegamePath=$MGBA_SAVE_DIR")
fi
TRACE_DIR="${QUINTRA_BALANCE_TRACE_DIR:-}"
DEBUG_DIR="${QUINTRA_BALANCE_DEBUG_DIR:-}"
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
mkdir -p "$TRIAL_DIR"
if [ -n "$TRACE_DIR" ]; then mkdir -p "$TRACE_DIR"; fi
if [ -n "$DEBUG_DIR" ]; then mkdir -p "$DEBUG_DIR"; fi
HEADER="run,class,seed,frames,max_room,rooms_seen,rooms_cleared,kills,bosses,damage,giant_overlap_damage,min_hp,final_x,final_y,world_mode,world_screen,room_frames,max_combat_frames,max_combat_room,max_combat_enemy,max_route_frames,max_route_room,hostiles,last_enemy,death_source,towns,world_hops,victory,ui_screen,dodges,shop_visits,purchases,enemy_mask,min_giant_hp,b_uses,boss_attempts,boss_attempt_frames,boss_clear_frames,town_market_visits,town_quarter_visits,boss_clear_durations"
if [ "$APPEND" != 1 ] || [ ! -s "$OUT" ]; then
  echo "$HEADER" > "$OUT"
fi

command -v "$MGBA_BIN" >/dev/null
for run in "${RUN_IDS[@]}"; do
  for class in "${CLASS_IDS[@]}"; do
    # Resume is idempotent.  A host timeout can arrive after mGBA's final CSV
    # append but before the wrapper reports completion; never run that same
    # deterministic seed/class pair twice when an experiment is resumed.
    if [ "$APPEND" = 1 ] && awk -F, -v run="$run" -v class="$class" '
      NR > 1 && $1 == run && $2 == class { found = 1; exit }
      END { exit found ? 0 : 1 }
    ' "$OUT"; then
      echo "[balance] run $run class $class already recorded; skipping"
      continue
    fi
    echo "[balance] run $run/$REPS class $class"
    completed=false
    # mGBA occasionally drops the Lua process before its final CSV append.
    # Retry just that controller-only trial once; a matrix is never silently
    # reported with a missing class/seed row.
    for attempt in 1 2; do
      # Never let a late mGBA process write into the shared matrix.  A row is
      # committed only after this attempt's own CSV has completed, which makes
      # interruption/resume deterministic instead of producing duplicate or
      # missing seed/class pairs.
      trial_csv=$(mktemp "$TRIAL_DIR/balance-$run-$class-attempt-$attempt.XXXXXX")
      echo "$HEADER" > "$trial_csv"
      before=$(wc -l < "$trial_csv")
      log="/tmp/quintra-balance-$run-$class-$attempt.log"
      trace_env=()
      debug_env=()
      if [ -n "$TRACE_DIR" ]; then
        trace_env+=("QUINTRA_BOT_TRACE_OUT=$TRACE_DIR/run-$run-class-$class-$attempt.trace")
      fi
      if [ -n "$DEBUG_DIR" ]; then
        debug_env+=("QUINTRA_BOT_DEBUG_OUT=$DEBUG_DIR/run-$run-class-$class-$attempt.log")
      fi
      env "${trace_env[@]}" "${debug_env[@]}" \
        QUINTRA_RS_ADDR="$RS" QUINTRA_PL_ADDR="$PL" QUINTRA_EN_ADDR="$EN" QUINTRA_TM_ADDR="$TM" \
        QUINTRA_SCREEN_ADDR="$LS" \
        QUINTRA_FRAME_ADDR="$FC" \
        QUINTRA_BOT_RUN="$run" QUINTRA_BOT_CLASS="$class" \
        QUINTRA_BOT_FRAMES="$FRAMES" QUINTRA_BOT_OUT="$trial_csv" \
        timeout "$HOST_TIMEOUT" "$MGBA_BIN" "${MGBA_SAVE_ARGS[@]}" "$ROM" --script "$ROOT/scripts/quintra_balance_bot.lua" -l 0 \
        >"$log" 2>&1 &
      pid=$!
      # This mGBA build does not honor frontend:quit from Lua reliably. The
      # completed CSV row is the transaction boundary; stop the wrapper then.
      for _ in $(seq 1 $((HOST_TIMEOUT * 4))); do
          now=$(wc -l < "$trial_csv")
          if [ "$now" -gt "$before" ]; then break; fi
          if ! kill -0 "$pid" 2>/dev/null; then break; fi
          sleep 0.25
      done
      # Headless mGBA exits once the Lua observer returns.  The timeout process
      # is the direct child here; avoiding background setsid prevents us from
      # mistaking its forked parent for a completed emulator.
      kill "$pid" 2>/dev/null || true
      wait "$pid" 2>/dev/null || true
      grep 'BALANCE' "$log" || true
      if [ "$now" -eq $((before + 1)) ]; then
        # A previous wrapper can finish while a resumed wrapper is already in
        # flight.  Serialize the final check-and-append: one and only one
        # controller process may commit a deterministic (run,class) result.
        if (
          flock -x 9
          if awk -F, -v run="$run" -v class="$class" '
            NR > 1 && $1 == run && $2 == class { found = 1; exit }
            END { exit found ? 0 : 1 }
          ' "$OUT"; then
            exit 2
          fi
          tail -n 1 "$trial_csv" >> "$OUT"
        ) 9>>"$OUT.lock"; then
          completed=true
          break
        else
          commit_status=$?
          if [ "$commit_status" -eq 2 ]; then
            echo "[balance] run $run class $class committed by another wrapper; skipping"
            completed=true
            break
          fi
          echo "[balance] ERROR could not commit run $run class $class" >&2
        fi
      fi
      echo "[balance] missing or duplicate trial row; retrying run $run class $class (attempt $attempt/2)" >&2
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
