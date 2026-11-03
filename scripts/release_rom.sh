#!/usr/bin/env bash
# Publish release notes for a verified commit without attaching the cartridge.
#
# GitHub otherwise defaults a newly created release tag to its default branch,
# which can differ from the verified release commit. This helper pins the tag
# to HEAD, then asks gh to verify that existing tag rather than inventing one.
#
# rom/working/quintra.gbc is a local build product. It is gitignored and is
# not a GitHub Release asset. preflight still builds it so the SHA-256 below
# is the cartridge this commit produced. The tag workflow in
# .github/workflows/release.yml also creates a Release (itch zip only) when
# the tag push arrives, so do not run this and that creator against the same
# new tag.
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
if [ ! -f "$ROM" ]; then
  echo "missing built cartridge: $ROM" >&2
  exit 2
fi
echo "Built cartridge (not uploaded; CI artifact name: quintra-gbc):"
sha256sum "$ROM"

COMMIT="$(git rev-parse HEAD)"
git push origin "$COMMIT:refs/tags/$VERSION"
env -u GH_TOKEN gh release create "$VERSION" --repo "$REPO" \
  --verify-tag --target "$COMMIT" --title "Quintra $VERSION" --notes-file "$NOTES_FILE"
