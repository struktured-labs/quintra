#!/usr/bin/env bash
# Build reproducible Quintra desktop packages for Linux x64 and Windows x64
# plus a SteamPipe-ready content tree. Never uploads anything.
# SPDX-License-Identifier: GPL-3.0-or-later
set -euo pipefail
umask 022

desktop=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
root=$(cd "$desktop/.." && pwd)
out="$root/builds/desktop"
steam="$root/builds/steam"
web_version=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["version"])' "$root/builds/itch-web/build.json")
version="${QUINTRA_DESKTOP_VERSION:-$web_version}"
if [[ ! "$version" =~ ^v[0-9]+\.[0-9]+\.[0-9]+(-[A-Za-z0-9.-]+)?$ ]]; then
  echo "Invalid desktop version: $version" >&2
  exit 1
fi
platforms="${QUINTRA_DESKTOP_PLATFORMS:-linux win}"

export SOURCE_DATE_EPOCH="${SOURCE_DATE_EPOCH:-$(git -C "$root" log -1 --format=%ct)}"
export ELECTRON_BUILDER_CACHE="${ELECTRON_BUILDER_CACHE:-$HOME/.cache/electron-builder}"
export CSC_IDENTITY_AUTO_DISCOVERY=false
stamp="@$SOURCE_DATE_EPOCH"

cd "$desktop"
[[ -d node_modules/electron ]] || npm ci --no-audit --no-fund
# Newer electron releases may defer the binary download; fetch it explicitly.
[[ -f node_modules/electron/dist/LICENSE ]] || node node_modules/electron/install.js
node scripts/stage.mjs

rm -rf "$out" "$steam/content" "$steam/scripts"
mkdir -p "$out" "$steam/content" "$steam/scripts" "$steam/output"

builder_args=()
for platform in $platforms; do
  case "$platform" in
    linux) builder_args+=(--linux dir) ;;
    win) builder_args+=(--win dir) ;;
    *) echo "Unknown platform $platform" >&2; exit 1 ;;
  esac
done
# Fixed mtimes and modes on everything that goes into app.asar.
find "$desktop/app" "$desktop/main.js" "$desktop/preload.js" "$desktop/package.json" \
  -exec touch -h -d "$stamp" {} +
npx --no-install electron-builder --config electron-builder.yml --x64 "${builder_args[@]}" \
  "-c.extraMetadata.version=${version#v}"

normalise() {
  find "$1" -exec touch -h -d "$stamp" {} +
  find "$1" -type d -exec chmod 755 {} +
  find "$1" -type f -perm -u+x -exec chmod 755 {} +
  find "$1" -type f ! -perm -u+x -exec chmod 644 {} +
}

# Steam depots and archives both use a "Quintra" top-level directory.
for platform in $platforms; do
  case "$platform" in
    linux) src="$out/electron/linux-unpacked"; depot="$steam/content/linux"; label=linux-x64 ;;
    win) src="$out/electron/win-unpacked"; depot="$steam/content/windows"; label=win-x64 ;;
  esac
  cp -a "$src" "$depot"
  normalise "$depot"
  stage_dir="$out/stage-$label"
  rm -rf "$stage_dir"
  mkdir -p "$stage_dir"
  cp -a "$depot" "$stage_dir/Quintra"
  normalise "$stage_dir"
  name="quintra-desktop-$version-$label"
  if [[ "$platform" == linux ]]; then
    tar --sort=name --mtime="$stamp" --owner=0 --group=0 --numeric-owner \
      --pax-option=exthdr.name=%d/PaxHeaders/%f,delete=atime,delete=ctime \
      -C "$stage_dir" -cf - Quintra | gzip -n -9 > "$out/$name.tar.gz"
  else
    (cd "$stage_dir" && find Quintra -print | LC_ALL=C sort | TZ=UTC zip -q -X -9 -@ "$out/$name.zip")
  fi
  rm -rf "$stage_dir"
done

# SteamPipe scripts from templates. IDs stay 0 until Steamworks issues them.
app_id="${STEAM_APP_ID:-0}"
depot_win="${STEAM_DEPOT_WINDOWS:-0}"
depot_linux="${STEAM_DEPOT_LINUX:-0}"
desc="Quintra $version ($(git -C "$root" rev-parse --short=12 HEAD))"
render() {
  sed -e "s|__STEAM_APP_ID__|$app_id|g" \
      -e "s|__STEAM_DEPOT_WINDOWS__|$depot_win|g" \
      -e "s|__STEAM_DEPOT_LINUX__|$depot_linux|g" \
      -e "s|__BUILD_DESC__|$desc|g" "$1" > "$2"
}
render "$desktop/steam/app_build.vdf.template" "$steam/scripts/app_build.vdf"
render "$desktop/steam/depot_build_windows.vdf.template" "$steam/scripts/depot_build_windows.vdf"
render "$desktop/steam/depot_build_linux.vdf.template" "$steam/scripts/depot_build_linux.vdf"
if [[ "$app_id" == 0 || "$depot_win" == 0 || "$depot_linux" == 0 ]]; then
  echo "NOTE: Steam app/depot IDs are placeholders (0). Set STEAM_APP_ID, STEAM_DEPOT_WINDOWS and STEAM_DEPOT_LINUX before any upload."
fi

(cd "$out" && sha256sum quintra-desktop-* > SHA256SUMS && cat SHA256SUMS)
ls -l "$out"/quintra-desktop-*
echo "SteamPipe content: $steam/content  scripts: $steam/scripts"
