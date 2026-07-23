#!/usr/bin/env bash
# Regression: an affordable optional counter must never trap the read-only
# Wolfkin pilot before the first sanctuary.  This fixed replay reaches the
# generated room-four counter after the earlier Sigil and sealed miniboss;
# it must then continue through the normal door route without a RAM write.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ROM="${1:-$ROOT/rom/working/quintra.gbc}"
OUT="$(mktemp /tmp/quintra-wolfkin-shop-exit.XXXXXX)"

QUINTRA_BALANCE_RUNS=4 QUINTRA_BALANCE_CLASSES=0 \
  QUINTRA_BALANCE_TARGET_FRAME=460 QUINTRA_BALANCE_FRAMES=3500 \
  QUINTRA_BALANCE_HOST_TIMEOUT=45 QUINTRA_BALANCE_OUT="$OUT" \
  QUINTRA_BALANCE_SKIP_REPORT=1 \
  bash "$ROOT/scripts/run_balance_bot.sh" "$ROM" >/dev/null

awk -F, '
  NR == 1 { for (i = 1; i <= NF; ++i) c[$i] = i; next }
  NR == 2 {
    if ($(c["seed"]) != 2064128647) exit 1
    if ($(c["shop_visits"]) < 1) exit 1
    if ($(c["max_room"]) < 5) exit 1
    ok = 1
  }
  END { exit ok ? 0 : 1 }
' "$OUT"

echo "[wolfkin-shop-exit] PASS optional counter yields to the forward route"
