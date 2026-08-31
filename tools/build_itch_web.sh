#!/usr/bin/env bash
set -euo pipefail

project_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
output_dir="$project_root/builds/itch-web"
archive="$project_root/builds/quintra-itch-web-v0.20.15-beta8.zip"
rom="$project_root/rom/working/quintra.gbc"
expected_rom_sha="3a2056c0642804d77d8b173636b0ee393659ad3b463c460d894c22a735c0d2e6"
wasmboy_sha="e3aeddf33d6ecf3c03adc1112787537c318d05b48c9e12fe2241416acffa804b"
version="v0.20.15-beta8"

actual_rom_sha=$(sha256sum "$rom" | cut -d' ' -f1)
if [[ "$actual_rom_sha" != "$expected_rom_sha" ]]; then
  echo "ROM hash mismatch: expected $expected_rom_sha, got $actual_rom_sha" >&2
  exit 1
fi

actual_wasmboy_sha=$(sha256sum "$project_root/web/itch/vendor/wasmboy-0.7.1.umd.js" | cut -d' ' -f1)
if [[ "$actual_wasmboy_sha" != "$wasmboy_sha" ]]; then
  echo "WasmBoy hash mismatch: expected $wasmboy_sha, got $actual_wasmboy_sha" >&2
  exit 1
fi

case "$output_dir" in
  "$project_root"/builds/itch-web) ;;
  *) echo "Refusing unsafe output directory: $output_dir" >&2; exit 1 ;;
esac

rm -rf "$output_dir"
mkdir -p "$output_dir/emulator" "$output_dir/licenses" "$output_dir/media" "$output_dir/patches"

cp "$project_root/web/itch/index.html" "$output_dir/index.html"
cp "$project_root/web/itch/player.css" "$output_dir/emulator/quintra-player.css"
cp "$project_root/web/itch/player.js" "$output_dir/emulator/quintra-player.js"
cp "$project_root/web/itch/vendor/wasmboy-0.7.1.umd.js" "$output_dir/emulator/wasmboy.js"
cp "$project_root/web/itch/vendor/WASMBOY-LICENSE.txt" "$output_dir/licenses/WASMBOY-LICENSE.txt"
cp "$project_root/web/itch/THIRD-PARTY-NOTICES.md" "$output_dir/licenses/THIRD-PARTY-NOTICES.md"
cp "$project_root/web/itch/patches/wasmboy-0.7.1-channel1-double-speed.patch" "$output_dir/patches/wasmboy-0.7.1-channel1-double-speed.patch"
cp "$project_root/web/itch/patches/wasmboy-0.7.1-audio-sync.patch" "$output_dir/patches/wasmboy-0.7.1-audio-sync.patch"
cp "$project_root/LICENSES/GPL-3.0-or-later.txt" "$output_dir/licenses/GPL-3.0-or-later.txt"
cp "$project_root/LICENSES/README.md" "$output_dir/licenses/QUINTRA-LICENSE-MAP.md"
cp "$project_root/docs/media/itch/quintra-cover-630x500.png" "$output_dir/media/cover.png"
cp "$rom" "$output_dir/quintra.gbc"

sed -i 's|href="player.css"|href="emulator/quintra-player.css"|' "$output_dir/index.html"
sed -i "s|__QUINTRA_WEB_VERSION__|$version|g" "$output_dir/index.html"

printf '%s  quintra.gbc\n' "$actual_rom_sha" > "$output_dir/quintra.sha256"

git_commit=$(git -C "$project_root" rev-parse HEAD)
cat > "$output_dir/build.json" <<JSON
{
  "version": "$version",
  "gitCommit": "$git_commit",
  "romSha256": "$actual_rom_sha",
  "emulator": "wasmboy-0.7.1+quintra.3",
  "emulatorCommit": "8e96bcb70969d943b1ffc4028b169c835098ce04",
  "emulatorSha256": "$actual_wasmboy_sha",
  "channel": "web"
}
JSON

python3 "$project_root/tools/test_itch_web.py" "$output_dir"
node "$project_root/tools/test_itch_gamepad.mjs" "$output_dir/emulator/quintra-player.js"

rm -f "$archive"
(cd "$output_dir" && zip -q -9 -r "$archive" .)

file_count=$(find "$output_dir" -type f | wc -l)
size_bytes=$(du -sb "$output_dir" | cut -f1)
largest_file=$(find "$output_dir" -type f -printf '%s %P\n' | sort -nr | head -1)

echo "Built $archive"
echo "Version: $version"
echo "ROM SHA-256: $actual_rom_sha"
echo "Files: $file_count"
echo "Extracted bytes: $size_bytes"
echo "Largest file: $largest_file"
