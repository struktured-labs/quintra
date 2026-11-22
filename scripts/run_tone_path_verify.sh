#!/bin/bash
# One headless build+test for the tone-path puzzle. Logs to a file; prints a short summary.
set -euo pipefail
export PATH=/home/struktured/.local/bin:$PATH
WT=/tmp/q-tonepath
LOG=${TONE_PATH_LOG:-/tmp/q-tonepath-verify.log}
export TONE_PATH_PREVIEW_DIR=${TONE_PATH_PREVIEW_DIR:-/tmp/q-tonepath-previews}
mkdir -p "$TONE_PATH_PREVIEW_DIR"
cd "$WT"
{
  echo "===== $(date) tone-path verify ====="
  echo "HEAD=$(git log -1 --oneline)"
  make -j"$(nproc)" rom/working/quintra.gbc
  python3 scripts/check_rom_layout.py rom/working/quintra
  uv run --quiet --with "pyboy==2.7.0" --with pillow python scripts/test_tone_path_block.py
  uv run --quiet --with "pyboy==2.7.0" --with pillow python scripts/test_new_game_start.py
  echo "===== ALL OK ====="
} >"$LOG" 2>&1
# Short summary only
if grep -q "===== ALL OK =====" "$LOG"; then
  echo "PASS: tone-path build+tests"
  grep -E '\[tone-path\]|\[layout\]|PASS|FAIL|Continue' "$LOG" | tail -20
  exit 0
else
  echo "FAIL: see $LOG"
  tail -40 "$LOG"
  exit 1
fi
