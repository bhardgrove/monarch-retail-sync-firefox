#!/usr/bin/env bash
# Build the test image and run test/run_test.py in headless Firefox ESR.
# Screenshots and the Firefox console log land in test/out/.
set -euo pipefail
cd "$(dirname "$0")/.."

# shellcheck disable=SC1091
[ -f local.env ] && { set -a; . ./local.env; set +a; }
python3 -I scripts/patch.py
docker build -q -t monarch-ff-test test >/dev/null
mkdir -p test/out
hosts=()
for h in app api shop report; do hosts+=(--add-host "$h.probe.test:127.0.0.1"); done
docker run --rm "${hosts[@]}" -v "$PWD:/work:ro" -v "$PWD/test/out:/out" -w /tmp \
  monarch-ff-test bash -c 'python3 -I /work/test/run_test.py 2>&1; rc=$?; exit $rc'
