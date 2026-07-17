#!/usr/bin/env bash
# Multi-seed controller completion gate. These four consecutive post-reward
# seeds exercise the normal dungeon/town/Riftwild route through all nine
# bosses using only real button input and procedural encounters.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ROM="${1:-$ROOT/rom/working/quintra.gbc}"
TMP="$(mktemp -d /tmp/quintra-picsean-endurance.XXXXXX)"
HOST_TIMEOUT="${QUINTRA_ENDURANCE_HOST_TIMEOUT:-240}"
RESULTS=()
for RUN in 13 14 15 16; do
  complete=false
  # mGBA can occasionally bus-error under simultaneous headless workers. Run
  # this controller contract one seed at a time, and retry only a missing
  # transaction once. A completed loss remains a real loss for the final
  # assertion; this retry is exclusively for emulator/process instability.
  for ATTEMPT in 1 2; do
    OUT="$TMP/run-$RUN-attempt-$ATTEMPT.csv"
    if QUINTRA_BALANCE_RUNS="$RUN" QUINTRA_BALANCE_CLASSES=3 \
      QUINTRA_BALANCE_FRAMES=90000 QUINTRA_BALANCE_HOST_TIMEOUT="$HOST_TIMEOUT" \
      QUINTRA_MGBA_SAVE_DIR="$TMP/save-$RUN-attempt-$ATTEMPT" \
      QUINTRA_BALANCE_OUT="$OUT" \
      bash "$ROOT/scripts/run_balance_bot.sh" "$ROM" >/dev/null; then
      RESULTS+=("$OUT")
      complete=true
      break
    fi
  done
  if [ "$complete" != true ]; then
    echo "[picsean-endurance] seed $RUN could not record after two isolated attempts" >&2
    exit 1
  fi
done

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
' "${RESULTS[@]}"
echo "[picsean-endurance] PASS four seeds completed all nine bosses"
