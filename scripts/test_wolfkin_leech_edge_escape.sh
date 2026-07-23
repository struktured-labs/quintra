#!/usr/bin/env bash
# Compatibility entry point for the former seed-dependent controller route.
# The actual Leech promise is narrower and stronger: a real player double-tap
# must release a real attached Leech.  Keep this name for existing local/CI
# callers while the long-route controller matrix remains a diagnostic gate.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
UV_CACHE_DIR="${UV_CACHE_DIR:-$ROOT/tmp/uv-cache}" \
  uv run --quiet --with pyboy python "$ROOT/scripts/test_leech_detach.py"
