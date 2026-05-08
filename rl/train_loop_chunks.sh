#!/bin/bash
# Wrapper: run train_shalamar_chunked.py in 5-epoch bursts, retry on hang.
# Each chunk has 90s timeout. If it hangs, kill and try next.

cd /home/struktured/projects/penta-dragon-dx-claude/rl
source .venv/bin/activate

LABEL="${1:-shalamar_ck}"
TOTAL_CHUNKS="${2:-50}"  # 50 chunks × 5 epochs = 250 epochs total
CHUNK_EPOCHS=5
STEPS=1024
LOG="logs/${LABEL}_chunked.log"

echo "==== Chunked training: $TOTAL_CHUNKS chunks of $CHUNK_EPOCHS epochs ====" >> "$LOG"
echo "Started: $(date)" >> "$LOG"

for i in $(seq 1 $TOTAL_CHUNKS); do
    echo "" >> "$LOG"
    echo "==== CHUNK $i/$TOTAL_CHUNKS ====" >> "$LOG"
    echo "$(date): starting chunk $i" >> "$LOG"
    timeout 90 python -u train_shalamar_chunked.py $CHUNK_EPOCHS $STEPS $LABEL >> "$LOG" 2>&1
    rc=$?
    echo "$(date): chunk $i exit=$rc" >> "$LOG"
    if [ $rc -eq 0 ]; then
        echo "  chunk $i: ok" >> "$LOG"
    elif [ $rc -eq 124 ]; then
        echo "  chunk $i: TIMEOUT (hang) — continuing" >> "$LOG"
    else
        echo "  chunk $i: error $rc" >> "$LOG"
    fi
done

echo "" >> "$LOG"
echo "==== ALL CHUNKS DONE: $(date) ====" >> "$LOG"
