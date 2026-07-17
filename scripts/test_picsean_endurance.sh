#!/usr/bin/env bash
# Multi-seed controller completion gate. These four seeds previously reached
# the town but could not leave its north gate; all must now finish the full
# nine-boss run through normal buttons and real procedural encounters.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ROM="${1:-$ROOT/rom/working/quintra.gbc}"
TMP="$(mktemp -d /tmp/quintra-picsean-endurance.XXXXXX)"
PIDS=()
for RUN in 4 5 8 9; do
  OUT="$TMP/run-$RUN.csv"
  QUINTRA_BALANCE_RUNS="$RUN" QUINTRA_BALANCE_CLASSES=3 \
    QUINTRA_BALANCE_FRAMES=90000 QUINTRA_BALANCE_HOST_TIMEOUT=120 \
    QUINTRA_BALANCE_OUT="$OUT" \
    bash "$ROOT/scripts/run_balance_bot.sh" "$ROM" >/dev/null &
  PIDS+=("$!")
done
for PID in "${PIDS[@]}"; do wait "$PID"; done

awk -F, '
  FNR == 1 { for (i = 1; i <= NF; ++i) col[$i] = i; next }
  {
    rows++
    if ($(col["victory"]) == 1 && $(col["bosses"]) == 9 && $(col["frames"]) < 90000) wins++
  }
  END {
    if (rows != 4 || wins != 4) {
      print "[picsean-endurance] expected four full controller wins" > "/dev/stderr"
      exit 1
    }
  }
' "$TMP"/run-*.csv
echo "[picsean-endurance] PASS four seeds completed all nine bosses"
