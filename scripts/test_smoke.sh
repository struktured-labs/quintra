#!/usr/bin/env bash
# Quintra smoke test — runs the ROM under headless mGBA + a Lua harness
# that takes screenshots at each major screen transition.
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
ROM="${1:-$PROJECT_DIR/rom/working/quintra.gbc}"
OUT_DIR="${QUINTRA_OUT_DIR:-$PROJECT_DIR/tmp/smoketest}"

if [ ! -f "$ROM" ]; then
    echo "FAIL: ROM not found: $ROM"
    exit 1
fi

mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/h_*.png

# Resolve run_state's WRAM address from the linker map so the Lua
# harness can drive by GAME STATE (room counter) instead of fixed
# frame counts — code-size changes shift timing and made timed walks
# land in the wrong rooms.
RS_ADDR=$(grep 'DEF _run_state ' "${ROM%.gbc}.noi" 2>/dev/null | awk '{print $3}')
PL_ADDR=$(grep 'DEF _player ' "${ROM%.gbc}.noi" 2>/dev/null | awk '{print $3}')
EN_ADDR=$(grep 'DEF _entities ' "${ROM%.gbc}.noi" 2>/dev/null | awk '{print $3}')
TM_ADDR=$(grep 'DEF _room_tilemap ' "${ROM%.gbc}.noi" 2>/dev/null | awk '{print $3}')
LS_ADDR=$(grep 'DEF _loop_current_screen ' "${ROM%.gbc}.noi" 2>/dev/null | awk '{print $3}')
PK_ADDR=$(grep 'DEF _room_puzzle_kind ' "${ROM%.gbc}.noi" 2>/dev/null | awk '{print $3}')
PLK_ADDR=$(grep 'DEF _room_puzzle_locked ' "${ROM%.gbc}.noi" 2>/dev/null | awk '{print $3}')

echo "[smoke] running $ROM under headless mGBA (run_state @ ${RS_ADDR:-unknown})..."
unset DISPLAY WAYLAND_DISPLAY
QT_QPA_PLATFORM=offscreen SDL_AUDIODRIVER=dummy \
    QUINTRA_OUT_DIR="$OUT_DIR" QUINTRA_RS_ADDR="$RS_ADDR" QUINTRA_PL_ADDR="$PL_ADDR" \
    QUINTRA_EN_ADDR="$EN_ADDR" QUINTRA_TM_ADDR="$TM_ADDR" QUINTRA_SCREEN_ADDR="$LS_ADDR" \
    QUINTRA_PUZZLE_KIND_ADDR="$PK_ADDR" QUINTRA_PUZZLE_LOCK_ADDR="$PLK_ADDR" \
    timeout 60 xvfb-run -a mgba-qt "$ROM" \
        --script "$SCRIPT_DIR/quintra_smoketest.lua" \
        -l 0 >"$OUT_DIR/emulator.log" 2>&1 &
EMU_PID=$!

# This mGBA build ignores Lua's frontend:quit. The final capture is the
# transaction boundary, so stop waiting as soon as the harness produced it.
for _ in $(seq 1 240); do
    if [ -f "$OUT_DIR/h_13_room_return.png" ]; then break; fi
    if ! kill -0 "$EMU_PID" 2>/dev/null; then break; fi
    sleep 0.25
done
kill "$EMU_PID" 2>/dev/null || true
wait "$EMU_PID" 2>/dev/null || true
grep -v 'Window\|Qt\|libpng' "$OUT_DIR/emulator.log" || true

pkill -9 -f 'Xvfb :' 2>/dev/null || true

PASS=0 FAIL=0 TOTAL=0
# check <name> <min_colors>: the screenshot must exist AND contain at
# least that many distinct colors. A blank frame is a single color — the
# old size-only check (>400B) passed on 411B all-white PNGs and let six
# boot-broken commits ship. Room-state assertions below supply the stronger
# progression check; room art intentionally uses compact, low-color palettes.
check() {
    local name="$1" mincol="${2:-8}"
    local f="$OUT_DIR/h_${name}.png"
    TOTAL=$((TOTAL+1))
    if [ ! -f "$f" ]; then
        echo "  FAIL $name (file missing)"; FAIL=$((FAIL+1)); return
    fi
    local ncol=$(python3 -c "
from PIL import Image
im = Image.open('$f').convert('RGB')
print(len(im.getcolors(16384)))" 2>/dev/null || echo 0)
    if [ "$ncol" -lt "$mincol" ]; then
        echo "  FAIL $name (${ncol} colors < ${mincol} — blank/degenerate frame)"
        FAIL=$((FAIL+1)); return
    fi
    echo "  PASS $name (${ncol} colors)"; PASS=$((PASS+1))
}

# assert_log <shot-name> <regex>: the debug.log line for that shot must
# match — catches "renders but game state is garbage" (open-bus reads).
assert_log() {
    local name="$1" pat="$2"
    TOTAL=$((TOTAL+1))
    if grep "SHOT ${name}" "$OUT_DIR/debug.log" 2>/dev/null | grep -q "$pat"; then
        echo "  PASS log:${name} ($pat)"; PASS=$((PASS+1))
    else
        echo "  FAIL log:${name} (wanted $pat, got: $(grep "SHOT ${name}" "$OUT_DIR/debug.log" 2>/dev/null | head -1))"
        FAIL=$((FAIL+1))
    fi
}

echo "[smoke] results in $OUT_DIR/"
check 01_title                2      # white-on-navy text between pulses
check 02_class_select         4
check 02b_sauran              4
check 02c_corvin              4
check 02d_picsean             4
check 02e_vespine             4
check 03_room0_enter          10
check 04_room1                7
check 05_room2_sigil          7
check 06_room5_branch         7
check 07_room9_threshold      7
# The first boss uses an intentional six-color night arena; its active-giant
# log assertion below verifies this is the actual encounter, not an empty UI.
check 08_BOSS_room            6
# 09-13 may legitimately be GAMEOVER/VICTORY screens (sparse colors) —
# the scripted player often dies to the bullet-hell boss. >=3 colors
# still rejects blank frames; progression is pinned by the log asserts.
check 09_boss_under_fire      3
check 10_boss_mid_fight       3
check 11_after_long_assault   3
check 12_pack                 2      # uniform menu palette is intentionally two-tone
check 13_room_return          3
# Exact state assertions use linker-resolved WRAM, not test-only sentinels.
# They prove every requested room was reached and the final room owns one
# active giant boss rather than merely resembling a boss screenshot.
# Wolfkin's seven-heart conference floor is 14 half-hearts at the first
# controllable room; keep the smoke contract tied to the real starter reserve.
assert_log 03_room0_enter     'room=0 .*giants=0 .*hp=14'
assert_log 04_room1           'room=1 '
assert_log 05_room2_sigil     'room=2 '
assert_log 06_room5_branch    'room=5 '
assert_log 07_room9_threshold 'room=9 '
assert_log 08_BOSS_room       'room=13 .*giants=1 '
assert_log 11_after_long_assault 'screen=5 .*room=13 .*bosses=1 .*giants=0 .*hp=[1-9]'
assert_log 12_pack            'screen=9 .*bosses=1 .*giants=0 .*hp=[1-9]'
assert_log 13_room_return     'screen=5 .*room=13 .*bosses=1 .*giants=0 .*hp=[1-9]'

echo "[smoke] $PASS/$TOTAL passed, $FAIL failed"
if [ "$FAIL" -gt 0 ]; then exit 1; fi
exit 0
