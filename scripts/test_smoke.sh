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

echo "[smoke] running $ROM under headless mGBA..."
unset DISPLAY WAYLAND_DISPLAY
QT_QPA_PLATFORM=offscreen SDL_AUDIODRIVER=dummy \
    QUINTRA_OUT_DIR="$OUT_DIR" \
    timeout 30 xvfb-run -a mgba-qt "$ROM" \
        --script "$SCRIPT_DIR/quintra_smoketest.lua" \
        -l 0 2>&1 | grep -v 'Window\|Qt\|libpng' || true

pkill -9 -f 'Xvfb :' 2>/dev/null || true

PASS=0 FAIL=0 TOTAL=0
# check <name> <min_colors>: the screenshot must exist AND contain at
# least that many distinct colors. A blank frame is a single color — the
# old size-only check (>400B) passed on 411B all-white PNGs and let six
# boot-broken commits ship. Color counting can't be fooled that way.
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
check 04_room1                10
check 05_room2                10
check 06_room3                10
check 07_room4                10
check 08_BOSS_room            10
check 09_boss_under_fire      10
check 10_boss_mid_fight       10
check 11_after_long_assault   10
check 12_paused               3      # dimmed palettes collapse colors
check 13_unpaused             10
# Game-state assertions: boss-room flag (0xFFFC == 0xBB) must be OFF in
# the first room and ON once the walk sequence reaches the boss.
assert_log 03_room0_enter     'boss=0x00'
assert_log 08_BOSS_room       'boss=0xBB'

echo "[smoke] $PASS/$TOTAL passed, $FAIL failed"
if [ "$FAIL" -gt 0 ]; then exit 1; fi
exit 0
