#!/bin/bash
cd /home/struktured/projects/penta-dragon-dx-claude/rl
source .venv/bin/activate
LABEL="${1:-explore_natural}"
TOTAL_CHUNKS="${2:-200}"
CHUNK_EPOCHS="${3:-2}"
STEPS="${4:-1024}"
TIMEOUT="${5:-90}"
LOG="logs/${LABEL}_chunked.log"
echo "==== Natural exploration: $TOTAL_CHUNKS chunks of $CHUNK_EPOCHS epochs ====" >> "$LOG"
for i in $(seq 1 $TOTAL_CHUNKS); do
    echo "" >> "$LOG"
    echo "==== CHUNK $i/$TOTAL_CHUNKS ====" >> "$LOG"
    echo "$(date): starting chunk $i" >> "$LOG"
    timeout $TIMEOUT python -u train_explore_natural.py $CHUNK_EPOCHS $STEPS $LABEL >> "$LOG" 2>&1
    rc=$?
    echo "$(date): chunk $i exit=$rc" >> "$LOG"
    if [ $rc -eq 0 ]; then echo "  chunk $i: ok" >> "$LOG"
    elif [ $rc -eq 124 ]; then echo "  chunk $i: TIMEOUT" >> "$LOG"
    else echo "  chunk $i: error $rc" >> "$LOG"
    fi
done
