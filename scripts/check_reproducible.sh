#!/usr/bin/env bash
# Build from a clean source copy and require byte-identical cartridge output.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d /tmp/quintra-repro.XXXXXX)"
JOBS="${QUINTRA_REPRO_JOBS:-4}"
KEEP="${QUINTRA_REPRO_KEEP:-0}"
cleanup() {
  if [ "$KEEP" != 1 ]; then rm -rf "$TMP"; fi
}
trap cleanup EXIT

rsync -a \
  --exclude .git --exclude obj --exclude target --exclude tmp \
  --exclude 'rom/working/quintra.gbc' \
  --exclude 'rom/working/quintra.map' \
  --exclude 'rom/working/quintra.noi' \
  "$ROOT/" "$TMP/"

# The source manifest and link order are explicitly sorted, so parallel
# compilation cannot perturb autobank placement. It does let a constrained
# builder start the large room unit immediately instead of spending most of
# its wall-clock budget compiling unrelated leaf files first. KEEP=1 retains
# this clean copy for diagnosis if a host interrupts the compiler.
# The clean-copy compiler can emit hundreds of command lines.  Keep this
# release gate's output focused on its actual contract (byte identity), while
# still preserving compiler diagnostics and the code generators' own output.
make --no-print-directory --silent -j "$JOBS" -C "$TMP" all
if ! cmp -s "$ROOT/rom/working/quintra.gbc" "$TMP/rom/working/quintra.gbc"; then
  echo "[repro] FAIL clean source copy produced different ROM bytes" >&2
  sha256sum "$ROOT/rom/working/quintra.gbc" "$TMP/rom/working/quintra.gbc" >&2
  exit 1
fi

echo "[repro] PASS byte-identical clean rebuild"
sha256sum "$ROOT/rom/working/quintra.gbc"
