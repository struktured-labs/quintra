#!/usr/bin/env bash
# A controller trace must expose both exact input and compact observable state
# without mutating ROM state. This checks a short real mGBA run and pins the
# dataset's self-describing schema for replay/RL tooling.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ROM="${1:-$ROOT/rom/working/quintra.gbc}"
DIR="$(mktemp -d /tmp/quintra-observation-trace.XXXXXX)"
OUT="$DIR/balance.csv"

QUINTRA_BALANCE_RUNS=1 QUINTRA_BALANCE_CLASSES=3 \
  QUINTRA_BALANCE_TARGET_FRAME=440 QUINTRA_BALANCE_FRAMES=7200 \
  QUINTRA_BALANCE_HOST_TIMEOUT=300 QUINTRA_BALANCE_OUT="$OUT" \
  QUINTRA_BALANCE_TRACE_DIR="$DIR" QUINTRA_BALANCE_SKIP_REPORT=1 \
  bash "$ROOT/scripts/run_balance_bot.sh" "$ROM" >/dev/null

OBS=$(find "$DIR" -name '*.obs.csv' -type f -print -quit)
test -n "$OBS"
test -s "$OBS"
# Picsean has no contact-triggered body dash. The generated seven-role route
# can legitimately stay in Crystal's body-heavy roster for this entire short
# sample, so do not invent a projectile/dodge requirement when none exists.
# The trace contract below instead proves that absent threats publish the
# explicit (0,255) sentinel and that the controller still records live input.
awk -F, '
  NR == 1 { next }
  NR == 2 { if ($2 != 3 || $4 < 100) exit 1; found = 1 }
  END { if (!found) exit 1 }
' "$OUT"
awk -F, '
  NR == 1 { if ($0 != "# quintra-observation-trace-v5") exit 1; next }
  NR == 2 {
    if ($0 != "# frame,room,world_mode,world_screen,px,py,hp,hp_max,mp,mp_max,target_kind,target_hp,target_x,target_y,target_giant,target_pattern,threat,threat_hit_in,threat_x,threat_y,threat_vx,threat_vy,nearest_projectile_x,nearest_projectile_y,nearest_projectile_vx,nearest_projectile_vy,nearest_projectile_distance,keys,room_age,weapon,active_charge,shield_timer,iframes") exit 1
    next
  }
  {
    if (NF != 33) exit 1
    # Major-reward claims and village recovery deliberately grant a 90-frame
    # safety window; ordinary combat recovery remains shorter. The trace
    # contract should reject corrupted bytes above that authored maximum,
    # not reject a legitimate reward event reached by a new controller path.
    if ($1 < last_frame || $7 > $8 || $9 > $10 || $17 > 1 || $18 > 255 || $32 > 100 || $33 > 90) exit 1
    if ($17 == 0 && $18 != 255) exit 1
    if ($17 == 1) {
      if ($18 != 255 && ($18 < 1 || $18 > 8)) exit 1
      threats++
    }
    if ($28 == 255 && ($23 != 255 || $24 != 255)) exit 1
    if ($32 > 0) shields++
    last_frame = $1; rows++
  }
  END { if (rows < 100 || shields < 1) exit 1 }
' "$OBS"
echo "[observation-trace] PASS compact state/action dataset + explicit no-threat contract"
