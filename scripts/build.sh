#!/usr/bin/env bash
# Patch upstream/ into build/, lint it with web-ext and zip it to dist/.
set -euo pipefail
cd "$(dirname "$0")/.."

# shellcheck disable=SC1091
[ -f local.env ] && { set -a; . ./local.env; set +a; }
python3 -I scripts/patch.py
version=$(python3 -I -c 'import json; print(json.load(open("build/manifest.json"))["version"])')

mkdir -p dist
docker run --rm -u "$(id -u):$(id -g)" -e HOME=/tmp -v "$PWD:/work" -w /work node:22-slim \
  npx -y web-ext@8 lint --source-dir build --self-hosted

rm -f "dist/monarch-retail-sync-$version.zip"
(cd build && python3 -I -c '
import sys, zipfile, os
with zipfile.ZipFile(sys.argv[1], "w", zipfile.ZIP_DEFLATED) as z:
    for d, _, fs in os.walk("."):
        for f in sorted(fs):
            p = os.path.join(d, f)[2:]
            z.write(p, p)
' "../dist/monarch-retail-sync-$version.zip")
echo "dist/monarch-retail-sync-$version.zip"
