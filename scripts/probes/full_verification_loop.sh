#!/bin/bash
# Full verification loop for Penta Dragon DX teleport ROM
# Runs ALL 8 tests 10 consecutive times
# Exits 0 only if ALL tests pass ALL 10 times

set -o pipefail

ROM="rom/working/penta_dragon_dx_teleport.gb"
LOGDIR="/tmp/penta_verify_loop_$(date +%s)"
mkdir -p "$LOGDIR"

echo "=== PENTA DRAGON DX — FULL VERIFICATION LOOP ==="
echo "ROM: $ROM"
echo "Log dir: $LOGDIR"
echo "Started: $(date)"
echo ""

cd /home/struktured/projects/penta-dragon-dx-claude

TARGET_PASSES=10
MAX_ATTEMPTS=100
pass_count=0

# Pre-build once
python3 scripts/build_v301_teleport.py > "$LOGDIR/prebuild.log" 2>&1
echo "Pre-build complete"
echo ""

for attempt in $(seq 1 $MAX_ATTEMPTS); do
    build_start=$(date +%s)
    echo "=== Attempt $attempt ==="
    
    # Rebuild
    python3 scripts/build_v301_teleport.py > "$LOGDIR/build_$attempt.log" 2>&1
    if [ ! -f "$ROM" ]; then
        echo "BUILD FAILED"
        cat "$LOGDIR/build_$attempt.log"
        exit 1
    fi
    
    rm -f "$LOGDIR/results_$attempt.txt"
    
    run_test() {
        local name="$1"
        local script="$2"
        local timeout_sec="$3"
        local logfile="$LOGDIR/attempt_${attempt}_${name}.log"
        timeout "$timeout_sec" python3 "$script" "$ROM" > "$logfile" 2>&1
        local rc=$?
        local status
        if [ $rc -eq 0 ]; then status="PASS"
        elif [ $rc -eq 124 ]; then status="TIMEOUT"
        else status="FAIL($rc)"
        fi
        echo "    $status — $name" >> "$LOGDIR/results_$attempt.txt"
        return $rc
    }
    
    # Run all tests sequentially 
    run_test "verify_title_animation_frames" "scripts/probes/verify_title_animation_frames.py" 180 &
    wait
    
    run_test "verify_flash_attribution" "scripts/probes/verify_flash_attribution.py" 300 &
    wait
    
    run_test "verify_title_color" "scripts/probes/verify_title_color.py" 120 &
    wait
    
    run_test "verify_gameplay_palette" "scripts/probes/verify_gameplay_palette.py" 180 &
    wait
    
    run_test "verify_miniboss_color" "scripts/probes/verify_miniboss_color.py" 240 &
    wait
    
    run_test "verify_scroll_tearing" "scripts/probes/verify_scroll_tearing.py" 240 &
    wait
    
    run_test "verify_phantom_d887" "scripts/probes/verify_phantom_d887.py" 240 &
    wait
    
    run_test "verify_boss_arena_palettes" "scripts/probes/verify_boss_arena_palettes.py" 600 &
    wait
    
    # Check results
    echo "  Results:"
    while IFS= read -r line; do
        echo "  $line"
        if echo "$line" | grep -q "FAIL\|TIMEOUT"; then
            all_passed=false
        fi
    done < "$LOGDIR/results_$attempt.txt"
    
    all_passed=true
    while IFS= read -r line; do
        if echo "$line" | grep -q "FAIL\|TIMEOUT"; then
            all_passed=false
        fi
    done < "$LOGDIR/results_$attempt.txt"
    
    build_elapsed=$(( $(date +%s) - build_start ))
    echo ""
    
    if $all_passed; then
        pass_count=$((pass_count + 1))
        echo "ATTEMPT $attempt: ALL 8 PASSED (${build_elapsed}s) — consecutive: $pass_count/$TARGET_PASSES"
        
        if [ $pass_count -ge $TARGET_PASSES ]; then
            echo ""
            echo "============================================"
            echo "  VERIFICATION COMPLETE — $TARGET_PASSES CONSECUTIVE PASSES"
            echo "============================================"
            echo "Finished: $(date)"
            echo ""
            echo "=== COMPILE OUTPUT (last build) ==="
            cat "$LOGDIR/build_$attempt.log"
            echo ""
            echo "=== FINAL TEST RESULTS ==="
            for test_name in verify_title_color verify_gameplay_palette verify_miniboss_color verify_scroll_tearing verify_phantom_d887 verify_title_animation_frames verify_boss_arena_palettes verify_flash_attribution; do
                echo ""
                echo "--- $test_name ---"
                tail -8 "$LOGDIR/attempt_${attempt}_${test_name}.log" 2>/dev/null | head -5
                tail -3 "$LOGDIR/attempt_${attempt}_${test_name}.log" 2>/dev/null
            done
            exit 0
        fi
    else
        echo "ATTEMPT $attempt: FAILURE (${build_elapsed}s) — resetting pass counter"
        pass_count=0
    fi
    echo ""
done

echo "FAILED: Exceeded $MAX_ATTEMPTS attempts without $TARGET_PASSES consecutive passes"
exit 1
