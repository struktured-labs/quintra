#!/usr/bin/env bash
# Run five honest controller-only agents against the built ROM.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ROM="${1:-$ROOT/rom/working/quintra.gbc}"
OUT="${QUINTRA_BALANCE_OUT:-$ROOT/tmp/balance-runs.csv}"
FRAMES="${QUINTRA_BALANCE_FRAMES:-10800}"
NOI="${ROM%.gbc}.noi"

RS=$(awk '/DEF _run_state / {print $3}' "$NOI")
PL=$(awk '/DEF _player / {print $3}' "$NOI")
EN=$(awk '/DEF _entities / {print $3}' "$NOI")
mkdir -p "$(dirname "$OUT")"
echo "class,frames,max_room,rooms_seen,rooms_cleared,kills,bosses,damage,min_hp" > "$OUT"

unset DISPLAY WAYLAND_DISPLAY
for class in 0 1 2 3 4; do
    echo "[balance] class $class"
    before=$(wc -l < "$OUT")
    log="/tmp/quintra-balance-$class.log"
    QT_QPA_PLATFORM=offscreen SDL_AUDIODRIVER=dummy \
      QUINTRA_RS_ADDR="$RS" QUINTRA_PL_ADDR="$PL" QUINTRA_EN_ADDR="$EN" \
      QUINTRA_BOT_CLASS="$class" QUINTRA_BOT_FRAMES="$FRAMES" QUINTRA_BOT_OUT="$OUT" \
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
pkill -9 -f 'Xvfb :' 2>/dev/null || true

python3 - "$OUT" <<'PY'
import csv, statistics, sys
rows = list(csv.DictReader(open(sys.argv[1])))
print(f"[balance] {len(rows)}/5 agents reported")
if rows:
    rooms = [int(r['max_room']) for r in rows]
    clears = [int(r['rooms_cleared']) for r in rows]
    print(f"[balance] median max room={statistics.median(rooms):g}; range={min(rooms)}..{max(rooms)}")
    print(f"[balance] median clears={statistics.median(clears):g}; raw={clears}")
if len(rows) != 5:
    raise SystemExit(1)
PY
echo "[balance] raw data: $OUT"
