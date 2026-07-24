#!/usr/bin/env bash
# Rebuild the README gameplay reel from the current cartridge runtime.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ROM="$ROOT/rom/working/quintra.gbc"
NOI="${ROM%.gbc}.noi"
OUT="$ROOT/docs/media/gameplay.gif"
META="$ROOT/docs/media/gameplay.json"
TMP="$(mktemp -d /tmp/quintra-media.XXXXXX)"
trap 'rm -rf "$TMP"' EXIT

if [ ! -f "$ROM" ] || [ ! -f "$NOI" ]; then
  echo "[media] missing built ROM/symbol map; run make media" >&2
  exit 1
fi
RS=$(awk '/DEF _run_state / {print $3}' "$NOI")
PL=$(awk '/DEF _player / {print $3}' "$NOI")
EN=$(awk '/DEF _entities / {print $3}' "$NOI")
TM=$(awk '/DEF _room_tilemap / {print $3}' "$NOI")
PZ=$(awk '/DEF _room_puzzle_locked / {print $3}' "$NOI")
if LC_ALL=C grep -aqE 'v0\.18\.(6[2-9]|[7-9][0-9])' "$ROM"; then
  MEDIA_TOPOLOGY=30
elif LC_ALL=C grep -aq 'v0.18.55' "$ROM"; then
  MEDIA_TOPOLOGY=12
elif LC_ALL=C grep -aqE 'v0\.18\.(58|59)' "$ROM"; then
  MEDIA_TOPOLOGY=16
elif grep -q 'DEF _run_state_boss_room ' "$NOI"; then
  MEDIA_TOPOLOGY=20
else
  MEDIA_TOPOLOGY=6
fi

status=0
# mGBA occasionally ignores Lua's frontend:quit, which made a successful
# 174-frame reel wait the full 120-second host timeout.  Put this capture in
# its own process group and treat its complete frame set as the transaction
# boundary, like the smoke and balance harnesses do.  Never kill a global
# Xvfb/mGBA process: users may be playing or debugging another ROM.
QT_QPA_PLATFORM=offscreen SDL_AUDIODRIVER=dummy \
QUINTRA_MEDIA_DIR="$TMP" QUINTRA_MEDIA_MODE=gif \
QUINTRA_MEDIA_TOPOLOGY="$MEDIA_TOPOLOGY" \
QUINTRA_RS_ADDR="$RS" QUINTRA_PL_ADDR="$PL" QUINTRA_EN_ADDR="$EN" \
QUINTRA_TM_ADDR="$TM" QUINTRA_PZ_ADDR="${PZ:-0}" \
setsid xvfb-run -a mgba-qt "$ROM" --fastforward \
  --script "$ROOT/scripts/capture_media.lua" -l 0 >"$TMP/emulator.log" 2>&1 &
EMU_PID=$!
frames=0
for _ in $(seq 1 480); do
  frames=$(find "$TMP" -maxdepth 1 -name 'gif_*.png' | wc -l)
  if [ "$frames" -eq 174 ]; then break; fi
  if ! kill -0 "$EMU_PID" 2>/dev/null; then break; fi
  sleep 0.25
done
kill -- -"$EMU_PID" 2>/dev/null || true
wait "$EMU_PID" 2>/dev/null || status=$?
if [ "$frames" -ne 174 ]; then
  grep -v 'Window\|Qt\|libpng' "$TMP/emulator.log" >&2 || true
  echo "[media] expected 174 captured frames, found $frames" >&2
  exit 1
fi

# The README still gallery is part of the same ROM-bound media transaction.
# Its former files could remain months behind the GIF because only the reel
# mode ran here. Capture the deterministic live rooms now and publish all eleven
# images together, including the abstract Compass, a real village, and the
# screen-scale boss.
QT_QPA_PLATFORM=offscreen SDL_AUDIODRIVER=dummy \
QUINTRA_MEDIA_DIR="$TMP" QUINTRA_MEDIA_MODE=shots \
QUINTRA_MEDIA_TOPOLOGY="$MEDIA_TOPOLOGY" \
QUINTRA_RS_ADDR="$RS" QUINTRA_PL_ADDR="$PL" QUINTRA_EN_ADDR="$EN" \
QUINTRA_TM_ADDR="$TM" QUINTRA_PZ_ADDR="${PZ:-0}" \
setsid xvfb-run -a mgba-qt "$ROM" --fastforward \
  --script "$ROOT/scripts/capture_media.lua" -l 0 >"$TMP/shots-emulator.log" 2>&1 &
SHOT_PID=$!
shots=0
for _ in $(seq 1 480); do
  shots=$(find "$TMP" -maxdepth 1 -name 'shot_*.png' | wc -l)
  if [ "$shots" -eq 12 ]; then break; fi
  if ! kill -0 "$SHOT_PID" 2>/dev/null; then break; fi
  sleep 0.25
done
kill -- -"$SHOT_PID" 2>/dev/null || true
wait "$SHOT_PID" 2>/dev/null || true
if [ "$shots" -ne 12 ]; then
  grep -v 'Window\|Qt\|libpng' "$TMP/shots-emulator.log" >&2 || true
  echo "[media] expected 12 README stills, found $shots" >&2
  exit 1
fi

cp "$TMP/shot_class.png" "$ROOT/docs/media/class.png"
cp "$TMP/shot_class2.png" "$ROOT/docs/media/class_preview.png"
cp "$TMP/shot_compass.png" "$ROOT/docs/media/compass.png"
cp "$TMP/shot_dungeon.png" "$ROOT/docs/media/dungeon.png"
cp "$TMP/shot_pack.png" "$ROOT/docs/media/pack.png"
cp "$TMP/shot_riftwild_map.png" "$ROOT/docs/media/riftwild-map.png"
cp "$TMP/shot_ember.png" "$ROOT/docs/media/ember.png"
cp "$TMP/shot_shop.png" "$ROOT/docs/media/shop.png"
cp "$TMP/shot_sanctuary.png" "$ROOT/docs/media/sanctuary.png"
cp "$TMP/shot_village.png" "$ROOT/docs/media/village.png"
cp "$TMP/shot_boss.png" "$ROOT/docs/media/boss.png"

# The CGB capture uses fewer than 32 visible colours, but ImageMagick's GIF
# writer otherwise allocates a 128-entry table. Pin the palette before delta
# optimization so the conference reel stays below the repository size budget.
magick -delay 10 -loop 0 "$TMP"/gif_*.png -dither None -colors 32 \
  -fuzz 1% -layers Optimize "$OUT"
UV_CACHE_DIR="${UV_CACHE_DIR:-$ROOT/tmp/uv-cache}" \
  uv run --quiet --with pyboy python "$ROOT/scripts/capture_title_media.py"
UV_CACHE_DIR="${UV_CACHE_DIR:-$ROOT/tmp/uv-cache}" \
  uv run --quiet --with "pyboy==2.7.0" --with pillow python \
  "$ROOT/scripts/capture_boss_gallery.py" --rom "$ROM" \
  --out "$ROOT/docs/media/boss-gallery.png" \
  --animated-out "$ROOT/docs/media/boss-gallery.gif"
version=$(sed -n 's/.*QUINTRA_VERSION "\([^"]*\)".*/\1/p' "$ROOT/src/game/version.h")
rom_sha=$(sha256sum "$ROM" | cut -d' ' -f1)
capture_sha=$(sha256sum "$ROOT/scripts/capture_media.lua" | cut -d' ' -f1)
gif_sha=$(sha256sum "$OUT" | cut -d' ' -f1)
title_sha=$(sha256sum "$ROOT/docs/media/title.png" | cut -d' ' -f1)
title_capture_sha=$(sha256sum "$ROOT/scripts/capture_title_media.py" | cut -d' ' -f1)
boss_gallery_sha=$(sha256sum "$ROOT/docs/media/boss-gallery.png" | cut -d' ' -f1)
boss_gallery_gif_sha=$(sha256sum "$ROOT/docs/media/boss-gallery.gif" | cut -d' ' -f1)
boss_gallery_capture_sha=$(sha256sum "$ROOT/scripts/capture_boss_gallery.py" | cut -d' ' -f1)
stills_sha=$(cat \
  "$ROOT/docs/media/boss.png" \
  "$ROOT/docs/media/class.png" \
  "$ROOT/docs/media/class_preview.png" \
  "$ROOT/docs/media/compass.png" \
  "$ROOT/docs/media/dungeon.png" \
  "$ROOT/docs/media/ember.png" \
  "$ROOT/docs/media/pack.png" \
  "$ROOT/docs/media/riftwild-map.png" \
  "$ROOT/docs/media/sanctuary.png" \
  "$ROOT/docs/media/shop.png" \
  "$ROOT/docs/media/village.png" | sha256sum | cut -d' ' -f1)
bytes=$(stat -c %s "$OUT")
printf '{\n  "version": "%s",\n  "rom_sha256": "%s",\n  "capture_sha256": "%s",\n  "gif_sha256": "%s",\n  "title_sha256": "%s",\n  "title_capture_sha256": "%s",\n  "boss_gallery_sha256": "%s",\n  "boss_gallery_gif_sha256": "%s",\n  "boss_gallery_capture_sha256": "%s",\n  "stills_sha256": "%s",\n  "frames": 174,\n  "width": 160,\n  "height": 144,\n  "frame_ms": 100,\n  "boss_gallery_frames": 16,\n  "boss_gallery_frame_ms": 120\n}\n' \
  "$version" "$rom_sha" "$capture_sha" "$gif_sha" "$title_sha" \
  "$title_capture_sha" "$boss_gallery_sha" "$boss_gallery_gif_sha" \
  "$boss_gallery_capture_sha" "$stills_sha" > "$META"
echo "[media] wrote $OUT ($bytes bytes, 174 frames)"
