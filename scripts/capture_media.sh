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

make -C "$ROOT" all
RS=$(awk '/DEF _run_state / {print $3}' "$NOI")
PL=$(awk '/DEF _player / {print $3}' "$NOI")
EN=$(awk '/DEF _entities / {print $3}' "$NOI")

status=0
QT_QPA_PLATFORM=offscreen SDL_AUDIODRIVER=dummy \
QUINTRA_MEDIA_DIR="$TMP" QUINTRA_MEDIA_MODE=gif \
QUINTRA_RS_ADDR="$RS" QUINTRA_PL_ADDR="$PL" QUINTRA_EN_ADDR="$EN" \
timeout 120 xvfb-run -a mgba-qt "$ROM" --fastforward \
  --script "$ROOT/scripts/capture_media.lua" -l 0 || status=$?
# This mGBA frontend sometimes ignores the Lua quit request; a complete
# 174-frame transaction followed by timeout is still a successful capture.
if [ "$status" -ne 0 ] && [ "$status" -ne 124 ]; then exit "$status"; fi
frames=$(find "$TMP" -maxdepth 1 -name 'gif_*.png' | wc -l)
if [ "$frames" -ne 174 ]; then
  echo "[media] expected 174 captured frames, found $frames" >&2
  exit 1
fi

magick -delay 10 -loop 0 "$TMP"/gif_*.png -filter point -resize 300% \
  -layers Optimize "$OUT"
version=$(sed -n 's/.*QUINTRA_VERSION "\([^"]*\)".*/\1/p' "$ROOT/src/game/version.h")
rom_sha=$(sha256sum "$ROM" | cut -d' ' -f1)
capture_sha=$(sha256sum "$ROOT/scripts/capture_media.lua" | cut -d' ' -f1)
gif_sha=$(sha256sum "$OUT" | cut -d' ' -f1)
bytes=$(stat -c %s "$OUT")
printf '{\n  "version": "%s",\n  "rom_sha256": "%s",\n  "capture_sha256": "%s",\n  "gif_sha256": "%s",\n  "frames": 174,\n  "width": 480,\n  "height": 432,\n  "frame_ms": 100\n}\n' \
  "$version" "$rom_sha" "$capture_sha" "$gif_sha" > "$META"
echo "[media] wrote $OUT ($bytes bytes, 174 frames)"
