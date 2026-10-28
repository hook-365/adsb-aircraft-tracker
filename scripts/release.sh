#!/usr/bin/env bash
# Cut a release: scripts/release.sh X.Y.Z
# The integration version lives in exactly two files that must agree:
#   custom_components/adsb_aircraft_tracker/manifest.json  (read by Home Assistant / HACS)
#   custom_components/adsb_aircraft_tracker/const.py       (INTEGRATION_VERSION: sw_version, User-Agent, card cache-buster)
# This script is the only thing that should change them. It writes both,
# commits "release: vX.Y.Z" and creates the annotated tag. You then push
# main + tag and create the GitHub release (HACS installs from releases).
set -euo pipefail
ver=${1:-}
[[ "$ver" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "usage: $0 X.Y.Z" >&2; exit 2; }
cd "$(dirname "$0")/.."
C=custom_components/adsb_aircraft_tracker
[[ -z "$(git status --porcelain --untracked-files=no)" ]] || { echo "working tree has uncommitted changes" >&2; exit 1; }
git rev-parse -q --verify "refs/tags/v$ver" >/dev/null && { echo "tag v$ver already exists" >&2; exit 1; }
python3 - "$ver" "$C" <<'PY'
import json, re, sys
ver, C = sys.argv[1:3]
p = f"{C}/manifest.json"; d = json.load(open(p)); d["version"] = ver
open(p, "w").write(json.dumps(d, indent=2) + "\n")
p = f"{C}/const.py"; s = open(p).read()
s, n = re.subn(r'^INTEGRATION_VERSION = "[^"]+"$', f'INTEGRATION_VERSION = "{ver}"', s, flags=re.M)
assert n == 1, "INTEGRATION_VERSION not found exactly once"
open(p, "w").write(s)
PY
scripts/check-version.sh
git add "$C/manifest.json" "$C/const.py"
git commit -q -m "release: v$ver"
git tag -a "v$ver" -m "Release v$ver"
echo "committed $(git rev-parse --short HEAD), tagged v$ver"
echo "next: git push origin $(git rev-parse --abbrev-ref HEAD) v$ver && gh release create v$ver --title 'v$ver — …' --notes-file …"
