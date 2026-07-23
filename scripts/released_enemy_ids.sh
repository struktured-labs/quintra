#!/usr/bin/env bash
# Print the complete dense generated enemy-ID range for controller coverage.
# Content/codegen owns N_ENEMIES; endurance must not duplicate a stale list.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HEADER="$ROOT/src/generated/enemies.h"
COUNT="$(awk '$1 == "#define" && $2 == "N_ENEMIES" { print $3; exit }' "$HEADER")"

case "$COUNT" in
  ''|*[!0-9]*)
    echo "[released-enemies] invalid N_ENEMIES in $HEADER" >&2
    exit 1
    ;;
esac
if [ "$COUNT" -lt 1 ]; then
  echo "[released-enemies] N_ENEMIES must be positive (got $COUNT)" >&2
  exit 1
fi

seq 0 "$((COUNT - 1))" | paste -sd ' ' -
