#!/bin/bash
# ============================================================================
# Penta Dragon DX - Unified Test Suite
# ============================================================================
# Runs all verification tests and reports pass/fail.
#
# Usage:
#   ./scripts/test_dx.sh              # Run all tests
#   ./scripts/test_dx.sh --quick      # Skip audio + speed (fast iteration)
#   ./scripts/test_dx.sh --build      # Build ROM first, then test
#   ./scripts/test_dx.sh --no-audio   # Skip audio test (needs PulseAudio)
#   ./scripts/test_dx.sh --rom path   # Test specific ROM
#
# Exit codes:
#   0 = All tests passed
#   1 = One or more tests failed
#   2 = Build/setup error
# ============================================================================

set -euo pipefail

PROJ="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPTS="$PROJ/scripts"
TMP="$PROJ/tmp/verify"

# Defaults
BUILD=false
QUICK=false
NO_AUDIO=false
DX_ROM=""
ORIG_ROM="$PROJ/rom/Penta Dragon (J).gb"

# Parse args
while [[ $# -gt 0 ]]; do
    case "$1" in
        --build)    BUILD=true; shift ;;
        --quick)    QUICK=true; shift ;;
        --no-audio) NO_AUDIO=true; shift ;;
        --rom)      DX_ROM="$2"; shift 2 ;;
        -h|--help)
            echo "Usage: $0 [--build] [--quick] [--no-audio] [--rom ROM_PATH]"
            exit 0
            ;;
        *) echo "Unknown option: $1"; exit 2 ;;
    esac
done

# Find DX ROM
if [[ -z "$DX_ROM" ]]; then
    if [[ -f "$PROJ/rom/working/penta_dragon_dx_v288.gb" ]]; then
        DX_ROM="$PROJ/rom/working/penta_dragon_dx_v288.gb"
    elif [[ -f "$PROJ/rom/working/penta_dragon_dx_FIXED.gb" ]]; then
        DX_ROM="$PROJ/rom/working/penta_dragon_dx_FIXED.gb"
    fi
fi

# Source setenv if present
if [[ -f "$PROJ/setenv.sh" ]]; then
    source "$PROJ/setenv.sh"
fi

# ============================================================================
# Setup
# ============================================================================

mkdir -p "$TMP"

# Clean old markers
rm -f "$PROJ"/DONE_VERIFY_* "$PROJ"/DONE_DUAL_*

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color
BOLD='\033[1m'

echo ""
echo -e "${BOLD}============================================================${NC}"
echo -e "${BOLD} PENTA DRAGON DX - TEST SUITE${NC}"
echo -e "${BOLD}============================================================${NC}"
echo ""

# ============================================================================
# Step 0: Build (optional)
# ============================================================================

if $BUILD; then
    echo -e "${CYAN}[BUILD]${NC} Building ROM..."
    LATEST_BUILD=$(ls -t "$SCRIPTS"/create_vblank_colorizer_v*.py 2>/dev/null | head -1)
    if [[ -z "$LATEST_BUILD" ]]; then
        echo -e "${RED}[BUILD] FAIL: No build script found${NC}"
        exit 2
    fi
    echo "  Using: $(basename "$LATEST_BUILD")"
    if ! cd "$PROJ" && uv run python "$LATEST_BUILD" > "$TMP/build.log" 2>&1; then
        echo -e "${RED}[BUILD] FAIL: Build failed. See $TMP/build.log${NC}"
        tail -5 "$TMP/build.log"
        exit 2
    fi
    echo -e "${GREEN}[BUILD] OK${NC}"

    # Update DX ROM path after build
    if [[ -f "$PROJ/rom/working/penta_dragon_dx_FIXED.gb" ]]; then
        DX_ROM="$PROJ/rom/working/penta_dragon_dx_FIXED.gb"
    fi
fi

# ============================================================================
# Verify prerequisites
# ============================================================================

if [[ ! -f "$DX_ROM" ]]; then
    echo -e "${RED}ERROR: DX ROM not found. Build first with --build or specify with --rom${NC}"
    echo "  Tried: $DX_ROM"
    exit 2
fi

echo "  DX ROM:   $(basename "$DX_ROM")"
echo "  Orig ROM: $(basename "$ORIG_ROM")"
echo ""

# Track results
declare -a TEST_NAMES
declare -a TEST_RESULTS
declare -a TEST_DETAILS
TOTAL=0
PASSED=0
FAILED=0
SKIPPED=0

record_result() {
    local name="$1"
    local result="$2"  # PASS, FAIL, SKIP, ERROR
    local detail="$3"
    TEST_NAMES+=("$name")
    TEST_RESULTS+=("$result")
    TEST_DETAILS+=("$detail")
    TOTAL=$((TOTAL + 1))
    case "$result" in
        PASS) PASSED=$((PASSED + 1)) ;;
        FAIL) FAILED=$((FAILED + 1)) ;;
        SKIP) SKIPPED=$((SKIPPED + 1)) ;;
        *)    FAILED=$((FAILED + 1)) ;;
    esac
}

# ============================================================================
# Test 1: Boot Verification
# ============================================================================

echo -e "${CYAN}[1/5] Boot Verification${NC}"
echo "  Starting game, checking FFC1=1..."

BOOT_OUTPUT=$(cd "$PROJ" && uv run python "$SCRIPTS/verify_boot.py" "$DX_ROM" 2>&1) || true
BOOT_EXIT=$?

if echo "$BOOT_OUTPUT" | grep -q "\[BOOT\] PASS"; then
    FFC1_LINE=$(echo "$BOOT_OUTPUT" | grep "FFC1=1" || echo "")
    record_result "Boot" "PASS" "Game starts OK. $FFC1_LINE"
    echo -e "  ${GREEN}PASS${NC} $FFC1_LINE"
else
    BOOT_ERR=$(echo "$BOOT_OUTPUT" | grep -E "Error|FAIL" | head -1 || echo "Unknown error")
    record_result "Boot" "FAIL" "$BOOT_ERR"
    echo -e "  ${RED}FAIL${NC} $BOOT_ERR"
fi

# ============================================================================
# Test 2: No-Crash Verification (60s)
# ============================================================================

if $QUICK; then
    echo -e "\n${YELLOW}[2/5] No-Crash (SKIPPED - quick mode)${NC}"
    record_result "No-Crash" "SKIP" "Skipped (--quick)"
else
    echo -e "\n${CYAN}[2/5] No-Crash Verification (60s gameplay)${NC}"
    echo "  Running 60s of gameplay with infinite HP..."

    CRASH_OUTPUT=$(cd "$PROJ" && uv run python "$SCRIPTS/verify_boot.py" --mode nocrash "$DX_ROM" 2>&1) || true

    if echo "$CRASH_OUTPUT" | grep -q "\[NO-CRASH\] PASS"; then
        STUCK_LINE=$(echo "$CRASH_OUTPUT" | grep "stuck" || echo "")
        record_result "No-Crash" "PASS" "60s gameplay OK. $STUCK_LINE"
        echo -e "  ${GREEN}PASS${NC} $STUCK_LINE"
    else
        CRASH_ERR=$(echo "$CRASH_OUTPUT" | grep -E "Error|FAIL|stuck" | head -1 || echo "Unknown")
        record_result "No-Crash" "FAIL" "$CRASH_ERR"
        echo -e "  ${RED}FAIL${NC} $CRASH_ERR"
    fi
fi

# ============================================================================
# Test 3: Color Verification
# ============================================================================

echo -e "\n${CYAN}[3/5] Color Verification${NC}"
echo "  Checking BG tile palettes and OBJ sprite palettes..."

COLOR_OUTPUT=$(cd "$PROJ" && uv run python "$SCRIPTS/verify_colors.py" "$DX_ROM" 2>&1) || true

if echo "$COLOR_OUTPUT" | grep -q "\[COLORS\] PASS"; then
    BG_LINE=$(echo "$COLOR_OUTPUT" | grep "BG tiles" || echo "")
    OBJ_LINE=$(echo "$COLOR_OUTPUT" | grep "OBJ sprites" || echo "")
    record_result "Colors" "PASS" "$BG_LINE; $OBJ_LINE"
    echo -e "  ${GREEN}PASS${NC}"
    echo "  $BG_LINE"
    echo "  $OBJ_LINE"
else
    COLOR_ERR=$(echo "$COLOR_OUTPUT" | grep -E "BG tiles|OBJ sprites|Error" | head -3)
    record_result "Colors" "FAIL" "$COLOR_ERR"
    echo -e "  ${RED}FAIL${NC}"
    echo "$COLOR_ERR" | while read -r line; do echo "  $line"; done
fi

# ============================================================================
# Test 4: Speed Verification
# ============================================================================

if $QUICK; then
    echo -e "\n${YELLOW}[4/5] Speed (SKIPPED - quick mode)${NC}"
    record_result "Speed" "SKIP" "Skipped (--quick)"
elif [[ ! -f "$ORIG_ROM" ]]; then
    echo -e "\n${YELLOW}[4/5] Speed (SKIPPED - no original ROM)${NC}"
    record_result "Speed" "SKIP" "Original ROM not found"
else
    echo -e "\n${CYAN}[4/5] Speed Verification${NC}"
    echo "  Walking RIGHT for 10s, comparing to original..."

    SPEED_OUTPUT=$(cd "$PROJ" && uv run python "$SCRIPTS/verify_speed.py" \
        --dx-rom "$DX_ROM" --orig-rom "$ORIG_ROM" 2>&1) || true

    if echo "$SPEED_OUTPUT" | grep -q "\[SPEED\] PASS"; then
        METRICS=$(echo "$SPEED_OUTPUT" | grep "scroll_ticks\|dc81_changes\|oam_changes" || echo "")
        record_result "Speed" "PASS" "Within 5% of original"
        echo -e "  ${GREEN}PASS${NC}"
        echo "$METRICS" | while read -r line; do echo "  $line"; done
    elif echo "$SPEED_OUTPUT" | grep -q "\[SPEED\] FAIL"; then
        SPEED_ERR=$(echo "$SPEED_OUTPUT" | grep "DEVIATION\|ratio" | head -3)
        record_result "Speed" "FAIL" "$SPEED_ERR"
        echo -e "  ${RED}FAIL${NC}"
        echo "$SPEED_ERR" | while read -r line; do echo "  $line"; done
    else
        SPEED_ERR=$(echo "$SPEED_OUTPUT" | tail -3)
        record_result "Speed" "FAIL" "Test error: $SPEED_ERR"
        echo -e "  ${RED}ERROR${NC}"
        echo "$SPEED_ERR" | while read -r line; do echo "  $line"; done
    fi
fi

# ============================================================================
# Test 5: Audio Verification
# ============================================================================

if $QUICK || $NO_AUDIO; then
    SKIP_REASON="--quick"
    $NO_AUDIO && SKIP_REASON="--no-audio"
    echo -e "\n${YELLOW}[5/5] Audio (SKIPPED - $SKIP_REASON)${NC}"
    record_result "Audio" "SKIP" "Skipped ($SKIP_REASON)"
elif [[ ! -f "$ORIG_ROM" ]]; then
    echo -e "\n${YELLOW}[5/5] Audio (SKIPPED - no original ROM)${NC}"
    record_result "Audio" "SKIP" "Original ROM not found"
elif ! command -v pactl &>/dev/null; then
    echo -e "\n${YELLOW}[5/5] Audio (SKIPPED - PulseAudio not available)${NC}"
    record_result "Audio" "SKIP" "PulseAudio not available"
else
    echo -e "\n${CYAN}[5/5] Audio Verification${NC}"
    echo "  Recording 15s from each ROM (this takes ~90s)..."

    AUDIO_OUTPUT=$(cd "$PROJ" && uv run python "$SCRIPTS/verify_audio.py" \
        --dx-rom "$DX_ROM" --orig-rom "$ORIG_ROM" 2>&1) || true

    if echo "$AUDIO_OUTPUT" | grep -q "\[AUDIO\] PASS"; then
        SILENCE=$(echo "$AUDIO_OUTPUT" | grep "silence ratio" || echo "")
        PHANTOM=$(echo "$AUDIO_OUTPUT" | grep "Phantom" || echo "")
        record_result "Audio" "PASS" "$SILENCE $PHANTOM"
        echo -e "  ${GREEN}PASS${NC}"
        echo "  $SILENCE"
        echo "  $PHANTOM"
    elif echo "$AUDIO_OUTPUT" | grep -q "\[AUDIO\] SKIP"; then
        record_result "Audio" "SKIP" "Skipped by test"
        echo -e "  ${YELLOW}SKIP${NC}"
    elif echo "$AUDIO_OUTPUT" | grep -q "\[AUDIO\] FAIL"; then
        AUDIO_ERR=$(echo "$AUDIO_OUTPUT" | grep -E "silence|Phantom|onset|Error" | head -5)
        record_result "Audio" "FAIL" "$AUDIO_ERR"
        echo -e "  ${RED}FAIL${NC}"
        echo "$AUDIO_ERR" | while read -r line; do echo "  $line"; done
    else
        AUDIO_ERR=$(echo "$AUDIO_OUTPUT" | tail -3)
        record_result "Audio" "FAIL" "Test error: $AUDIO_ERR"
        echo -e "  ${RED}ERROR${NC}"
        echo "$AUDIO_ERR" | while read -r line; do echo "  $line"; done
    fi
fi

# ============================================================================
# Summary
# ============================================================================

echo ""
echo -e "${BOLD}============================================================${NC}"
echo -e "${BOLD} TEST RESULTS${NC}"
echo -e "${BOLD}============================================================${NC}"
echo ""

# Print table
printf "  %-15s %-8s %s\n" "TEST" "RESULT" "DETAILS"
printf "  %-15s %-8s %s\n" "----" "------" "-------"

for i in "${!TEST_NAMES[@]}"; do
    name="${TEST_NAMES[$i]}"
    result="${TEST_RESULTS[$i]}"
    detail="${TEST_DETAILS[$i]}"

    case "$result" in
        PASS) color="${GREEN}" ;;
        FAIL) color="${RED}" ;;
        SKIP) color="${YELLOW}" ;;
        *)    color="${RED}" ;;
    esac

    # Truncate detail to 60 chars for table
    if [[ ${#detail} -gt 60 ]]; then
        detail="${detail:0:57}..."
    fi

    printf "  %-15s ${color}%-8s${NC} %s\n" "$name" "$result" "$detail"
done

echo ""
echo -e "  ${BOLD}Total: $TOTAL${NC}  ${GREEN}Passed: $PASSED${NC}  ${RED}Failed: $FAILED${NC}  ${YELLOW}Skipped: $SKIPPED${NC}"
echo ""

if [[ $FAILED -eq 0 ]]; then
    echo -e "${GREEN}${BOLD}  ALL TESTS PASSED${NC}"
    echo ""
    exit 0
else
    echo -e "${RED}${BOLD}  $FAILED TEST(S) FAILED${NC}"
    echo ""
    echo "  Reports saved to: $TMP/"
    echo ""
    exit 1
fi
