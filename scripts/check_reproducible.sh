#!/usr/bin/env bash
# Build from a clean source copy and require byte-identical cartridge output.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d /tmp/quintra-repro.XXXXXX)"
trap 'rm -rf "$TMP"' EXIT

rsync -a \
  --exclude .git --exclude obj --exclude target --exclude tmp \
  --exclude 'rom/working/quintra.gbc' \
  --exclude 'rom/working/quintra.map' \
  --exclude 'rom/working/quintra.noi' \
  "$ROOT/" "$TMP/"

make --no-print-directory -C "$TMP" all
if ! cmp -s "$ROOT/rom/working/quintra.gbc" "$TMP/rom/working/quintra.gbc"; then
  echo "[repro] FAIL clean source copy produced different ROM bytes" >&2
  sha256sum "$ROOT/rom/working/quintra.gbc" "$TMP/rom/working/quintra.gbc" >&2
  exit 1
fi

echo "[repro] PASS byte-identical clean rebuild"
sha256sum "$ROOT/rom/working/quintra.gbc"
