#!/usr/bin/env bash
# Download the current Monarch Retail Sync build from the Chrome Web Store and
# unpack it into upstream/ (replacing whatever was there).
set -euo pipefail
cd "$(dirname "$0")/.."

EXT_ID=imfcckkmcklambpijbgcebggegggkgla
mkdir -p dl
curl -fsSL -o dl/upstream.crx \
  "https://clients2.google.com/service/update2/crx?response=redirect&prodversion=150.0&acceptformat=crx2,crx3&x=id%3D${EXT_ID}%26uc"

rm -rf upstream
python3 -I - dl/upstream.crx upstream <<'EOF'
import sys, zipfile
# A CRX3 is a header followed by a zip; zipfile finds the central directory from the end.
zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])
EOF
python3 -I -c 'import json,sys; print("upstream version", json.load(open(sys.argv[1]))["version"])' upstream/manifest.json
