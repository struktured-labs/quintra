#!/usr/bin/env bash
set -euo pipefail

project_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
publish=false

if [[ "${1:-}" == "--publish" ]]; then
  publish=true
elif [[ $# -ne 0 ]]; then
  echo "Usage: tools/deploy_itch.sh [--publish]" >&2
  exit 2
fi

"$project_root/tools/build_itch_web.sh"

if [[ "$publish" != true ]]; then
  echo "Validation complete; no upload performed. Re-run with --publish to push the web channel."
  exit 0
fi

butler push \
  --if-changed \
  --userversion v0.20.19-beta23 \
  "$project_root/builds/itch-web" \
  struktured/quintra:web
