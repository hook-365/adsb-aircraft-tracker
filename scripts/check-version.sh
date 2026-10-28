#!/usr/bin/env bash
# Fails unless manifest.json and const.py agree (and, on a tag build, match the tag).
set -euo pipefail
cd "$(dirname "$0")/.."
C=custom_components/adsb_aircraft_tracker
M=$(python3 -c "import json;print(json.load(open('$C/manifest.json'))['version'])")
K=$(sed -n 's/^INTEGRATION_VERSION = "\([^"]*\)"$/\1/p' "$C/const.py")
echo "manifest.json=$M const.py=$K ref=${GITHUB_REF_NAME:-local}"
[[ -n "$K" ]] || { echo "::error::INTEGRATION_VERSION not found in const.py"; exit 1; }
[[ "$M" == "$K" ]] || { echo "::error::manifest.json ($M) != const.py ($K) — use scripts/release.sh"; exit 1; }
if [[ "${GITHUB_REF_TYPE:-}" == "tag" ]]; then
  [[ "${GITHUB_REF_NAME}" == "v$M" ]] || { echo "::error::tag ${GITHUB_REF_NAME} != v$M"; exit 1; }
fi
echo "version OK: $M"
