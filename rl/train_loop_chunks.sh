#!/bin/bash
# Wrapper: run train_shalamar_chunked.py in 5-epoch bursts, retry on hang.
# Each chunk has 90s timeout. If it hangs, kill and try next.

cd /home/struktured/projects/penta-dragon-dx-claude/rl
source .venv/bin/activate

LABEL="${1:-shalamar_ck}"
TOTAL_CHUNKS="${2:-50}"  # 50 chunks × 2 epochs = 100 epochs total (when ALL succeed)
CHUNK_EPOCHS="${3:-2}"
STEPS="${4:-1024}"
TIMEOUT="${5:-60}"
LOG="logs/${LABEL}_chunked.log"

echo "==== Chunked training: $TOTAL_CHUNKS chunks of $CHUNK_EPOCHS epochs ====" >> "$LOG"
echo "Started: $(date)" >> "$LOG"

for i in $(seq 1 $TOTAL_CHUNKS); do
    echo "" >> "$LOG"
    echo "==== CHUNK $i/$TOTAL_CHUNKS ====" >> "$LOG"
    echo "$(date): starting chunk $i" >> "$LOG"
    timeout $TIMEOUT python -u train_shalamar_chunked.py $CHUNK_EPOCHS $STEPS $LABEL >> "$LOG" 2>&1
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
