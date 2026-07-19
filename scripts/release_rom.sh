#!/usr/bin/env bash
# Publish a source-pinned Quintra ROM release.
#
# GitHub otherwise defaults a newly created release tag to its default branch,
# which can differ from the verified release commit. This helper makes the
# source/binary relationship explicit: preflight, ensure the committed ROM is
# the one being uploaded, create the remote tag at HEAD, then ask gh to verify
# that existing tag rather than inventing one.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

VERSION="${1:-$(sed -n 's/^#define QUINTRA_VERSION "\([^"]*\)"$/\1/p' src/game/version.h)}"
NOTES_FILE="${2:-}"
ROM="rom/working/quintra.gbc"
REPO="struktured-labs/quintra"

if [ -z "$VERSION" ] || [ -z "$NOTES_FILE" ]; then
  echo "usage: $0 [vX.Y.Z] <release-notes-file>" >&2
  exit 2
fi
if [ ! -f "$NOTES_FILE" ]; then
  echo "release notes file not found: $NOTES_FILE" >&2
  exit 2
fi
if ! git diff --quiet; then
  echo "tracked worktree changes present; commit the release first" >&2
  exit 2
fi
if git ls-remote --exit-code --tags origin "refs/tags/$VERSION" >/dev/null 2>&1; then
  echo "remote tag already exists: $VERSION" >&2
  exit 2
fi

make -s preflight
if ! git diff --quiet HEAD -- "$ROM"; then
  echo "$ROM differs from HEAD; commit the verified ROM before publishing" >&2
  exit 2
fi

COMMIT="$(git rev-parse HEAD)"
git push origin "$COMMIT:refs/tags/$VERSION"
env -u GH_TOKEN gh release create "$VERSION" "$ROM" --repo "$REPO" \
  --verify-tag --target "$COMMIT" --title "Quintra $VERSION" --notes-file "$NOTES_FILE"
