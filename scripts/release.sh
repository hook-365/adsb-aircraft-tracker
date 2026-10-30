#!/usr/bin/env bash
# Cut a release: scripts/release.sh X.Y.Z [--push]
#
# The integration version lives in exactly two files that must agree:
#   custom_components/adsb_aircraft_tracker/manifest.json  (read by Home Assistant / HACS)
#   custom_components/adsb_aircraft_tracker/const.py       (INTEGRATION_VERSION: sw_version, User-Agent, card cache-buster)
# This script is the only thing that should change them.
#
# Release notes come from CHANGELOG.md: the "## [Unreleased]" section must be
# non-empty. It is renamed to "## [X.Y.Z] - YYYY-MM-DD", a fresh empty
# Unreleased section is added above it, and the compare/tag links at the
# bottom are updated. That section becomes the GitHub release body, which
# HACS shows users when it offers the update.
#
# Without --push it commits "release: vX.Y.Z" and creates the annotated tag,
# then prints the push + gh commands. With --push it also pushes main + tag
# and creates the GitHub release (HACS installs from releases).
set -euo pipefail
ver=${1:-}; push=${2:-}
[[ "$ver" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "usage: $0 X.Y.Z [--push]" >&2; exit 2; }
[[ -z "$push" || "$push" == "--push" ]] || { echo "usage: $0 X.Y.Z [--push]" >&2; exit 2; }
cd "$(dirname "$0")/.."
C=custom_components/adsb_aircraft_tracker
[[ -z "$(git status --porcelain --untracked-files=no)" ]] || { echo "working tree has uncommitted changes" >&2; exit 1; }
git rev-parse -q --verify "refs/tags/v$ver" >/dev/null && { echo "tag v$ver already exists" >&2; exit 1; }
notes=$(mktemp)
python3 - "$ver" "$C" "$notes" <<'PY'
import datetime, json, re, sys
ver, C, notes_path = sys.argv[1:4]
# --- version files ---
p = f"{C}/manifest.json"; d = json.load(open(p)); d["version"] = ver
open(p, "w").write(json.dumps(d, indent=2) + "\n")
p = f"{C}/const.py"; s = open(p).read()
s, n = re.subn(r'^INTEGRATION_VERSION = "[^"]+"$', f'INTEGRATION_VERSION = "{ver}"', s, flags=re.M)
assert n == 1, "INTEGRATION_VERSION not found exactly once"
open(p, "w").write(s)
# --- changelog ---
s = open("CHANGELOG.md").read()
m = re.search(r"^## \[Unreleased\]\n(.*?)(?=^## \[)", s, flags=re.M | re.S)
assert m, "CHANGELOG.md has no '## [Unreleased]' section followed by a version section"
body = m.group(1).strip()
assert body, "CHANGELOG.md: the Unreleased section is empty — write the release notes first"
prev = re.search(r"^## \[(\d+\.\d+\.\d+)\]", s[m.end():], flags=re.M).group(1)
today = datetime.date.today().isoformat()
repo = "https://github.com/hook-365/adsb-aircraft-tracker"
s = s[:m.start()] + f"## [Unreleased]\n\n## [{ver}] - {today}\n\n{body}\n\n" + s[m.end():]
s = re.sub(r"^\[Unreleased\]: .*$",
           f"[Unreleased]: {repo}/compare/v{ver}...HEAD\n[{ver}]: {repo}/releases/tag/v{ver}",
           s, count=1, flags=re.M)
open("CHANGELOG.md", "w").write(s)
open(notes_path, "w").write(body + "\n")
PY
scripts/check-version.sh
git add "$C/manifest.json" "$C/const.py" CHANGELOG.md
git commit -q -m "release: v$ver"
git tag -a "v$ver" -m "Release v$ver"
echo "committed $(git rev-parse --short HEAD), tagged v$ver"
title=$(sed -n 's/^- \*\*\([^*]*\)\*\*.*/\1/p' "$notes" | head -1 | sed 's/\.$//')
title="v$ver${title:+ — $title}"
branch=$(git rev-parse --abbrev-ref HEAD)
if [[ "$push" == "--push" ]]; then
  git push origin "$branch" "v$ver"
  gh release create "v$ver" --title "$title" --notes-file "$notes"
else
  echo "release notes written to $notes"
  echo "next: git push origin $branch v$ver && gh release create v$ver --title '$title' --notes-file $notes"
fi
