#!/usr/bin/env bash
# Submit build/ to addons.mozilla.org as an unlisted (self-distributed) add-on
# and download the signed .xpi into dist/.
#
# Needs GECKO_ID in local.env and AMO API credentials in ~/.config/amo/credentials;
# scripts/setup.sh creates both.
set -euo pipefail
cd "$(dirname "$0")/.."

# shellcheck disable=SC1091
[ -f local.env ] && { set -a; . ./local.env; set +a; }
if [ -z "${GECKO_ID:-}" ]; then
  echo "Set GECKO_ID in local.env first (run scripts/setup.sh)" >&2
  exit 1
fi

creds=${AMO_CREDENTIALS:-$HOME/.config/amo/credentials}
# shellcheck disable=SC1090
source "$creds"

scripts/build.sh
version=$(python3 -I -c 'import json; print(json.load(open("build/manifest.json"))["version"])')
docker run --rm -u "$(id -u):$(id -g)" -e HOME=/tmp \
  -e WEB_EXT_API_KEY="$AMO_JWT_ISSUER" -e WEB_EXT_API_SECRET="$AMO_JWT_SECRET" \
  -v "$PWD:/work" -w /work node:22-slim \
  npx -y web-ext@8 sign --channel unlisted --source-dir build --artifacts-dir dist/signing \
    --approval-timeout 900000
mv dist/signing/*.xpi "dist/monarch-retail-sync-$version-signed.xpi"
rmdir dist/signing
ls -l "dist/monarch-retail-sync-$version-signed.xpi"
