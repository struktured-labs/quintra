#!/usr/bin/env bash
# Regression: long-form controller endurance must require every generated
# enemy. New content used to require editing a hand-written 0..29 string.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HEADER="$ROOT/src/generated/enemies.h"
EXPECTED="$(bash "$ROOT/scripts/released_enemy_ids.sh")"
COUNT="$(awk '$1 == "#define" && $2 == "N_ENEMIES" { print $3; exit }' "$HEADER")"
ACTUAL="$(awk '$1 == "#define" && $2 ~ /^ENEMY_/ { print $3 }' "$HEADER" \
  | sort -n | paste -sd ' ' -)"

if [ "$EXPECTED" != "$ACTUAL" ]; then
  echo "[enemy-coverage] generated IDs are not dense 0..N-1" >&2
  echo "  expected: $EXPECTED" >&2
  echo "  actual:   $ACTUAL" >&2
  exit 1
fi
if ! grep -Fq 'QUINTRA_BALANCE_REQUIRED_ENEMIES="$$(bash scripts/released_enemy_ids.sh)"' \
  "$ROOT/Makefile"; then
  echo "[enemy-coverage] endurance does not derive generated roster IDs" >&2
  exit 1
fi
if [ "$(wc -w <<<"$EXPECTED")" -ne "$COUNT" ]; then
  echo "[enemy-coverage] roster count does not match generated ID list" >&2
  exit 1
fi

echo "[enemy-coverage] PASS all $COUNT generated enemy IDs feed endurance"
