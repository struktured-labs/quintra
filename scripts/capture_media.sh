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
# mGBA occasionally ignores Lua's frontend:quit, which made a successful
# 174-frame reel wait the full 120-second host timeout.  Put this capture in
# its own process group and treat its complete frame set as the transaction
# boundary, like the smoke and balance harnesses do.  Never kill a global
# Xvfb/mGBA process: users may be playing or debugging another ROM.
QT_QPA_PLATFORM=offscreen SDL_AUDIODRIVER=dummy \
QUINTRA_MEDIA_DIR="$TMP" QUINTRA_MEDIA_MODE=gif \
QUINTRA_RS_ADDR="$RS" QUINTRA_PL_ADDR="$PL" QUINTRA_EN_ADDR="$EN" \
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
