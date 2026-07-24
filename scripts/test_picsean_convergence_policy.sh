#!/usr/bin/env bash
# Regression: Picsean's controller must answer a full-MP giant with an actual
# cartridge ability, not drift into a body collision. A safe lane may use the
# ordinary A+B Spirit Convergence (MP 0, 180-frame charge); an imminent body
# collision may correctly choose the authored B Undertow guard (MP down two,
# 140-frame cooldown). The separate convergence-transform ROM test owns the
# mechanics of A+B itself. This policy check writes neither ROM nor cartridge
# RAM.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ROM="${1:-$ROOT/rom/working/quintra.gbc}"
TMP="$(mktemp -d /tmp/quintra-picsean-convergence.XXXXXX)"
trap 'rm -rf "$TMP"' EXIT

QUINTRA_BALANCE_RUNS=4 QUINTRA_BALANCE_CLASSES=3 \
  QUINTRA_BALANCE_TARGET_FRAME=460 QUINTRA_BALANCE_FRAMES=13000 \
  QUINTRA_BALANCE_HOST_TIMEOUT=90 QUINTRA_BALANCE_TRACE_DIR="$TMP/traces" \
  QUINTRA_BALANCE_OUT="$TMP/run.csv" QUINTRA_BALANCE_SKIP_REPORT=1 \
  bash "$ROOT/scripts/run_balance_bot.sh" "$ROM" >/dev/null

awk -F, '
  NR == 1 { for (i = 1; i <= NF; ++i) c[$i] = i; next }
  NR == 2 {
    if ($(c["seed"]) != 2064128647) {
      print "[picsean-convergence] fixed world drifted" > "/dev/stderr"; exit 1
    }
  }
' "$TMP/run.csv"

OBS="$TMP/traces/run-4-class-3-1.obs.csv"
awk -F, '
  function abs(v) { return v < 0 ? -v : v }
  function cheb(x1, y1, x2, y2) {
    dx = abs(x1 - x2); dy = abs(y1 - y2)
    return dx > dy ? dx : dy
  }
  NR == 1 { next }
  NR == 2 {
    sub(/^# /, "")
    for (i = 1; i <= NF; ++i) c[$i] = i
    next
  }
  $(c["target_kind"]) == 1 && $(c["target_giant"]) != 0 && $(c["mp"]) == 0 \
    && $(c["active_charge"]) >= 175 { found = 1 }
  $(c["target_kind"]) == 1 && $(c["target_giant"]) != 0 \
    && $(c["mp"]) <= $(c["mp_max"]) - 2 \
    && $(c["active_charge"]) >= 130 && $(c["active_charge"]) <= 140 \
    && cheb($(c["px"]), $(c["py"]), $(c["target_x"]), $(c["target_y"])) <= 44 { found = 1 }
  END {
    if (!found) {
      print "[picsean-convergence] giant never received a real full-meter response" > "/dev/stderr"
      exit 1
    }
  }
' "$OBS"

echo "[picsean-convergence] PASS full-MP giant response reached cartridge state"
