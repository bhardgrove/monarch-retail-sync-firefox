#!/usr/bin/env python3
"""Turn the unpacked Chrome build in upstream/ into a Firefox build in build/.

Mostly a manifest change; the code is WXT-built and already uses
globalThis.browser when it exists. The one code edit follows from moving the
DNR permission to required, plus hand-built chrome-extension:// links.
"""
import json
import os
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "upstream"
OUT = ROOT / "build"

# Your own add-on id (set in local.env, see README). AMO ties an id to the
# account that first signed it, so every user needs a different one.
DEV_GECKO_ID = "monarch-retail-sync-dev@example.invalid"
GECKO_ID = os.environ.get("GECKO_ID") or DEV_GECKO_ID
MIN_FIREFOX = "128.0"  # DNR modifyHeaders
# Bump when re-releasing the same upstream version with a different patch;
# AMO never accepts the same version twice.
PATCH_LEVEL = 2


def main():
    if not (SRC / "manifest.json").exists():
        sys.exit("upstream/ is empty; run scripts/fetch.sh first")

    shutil.rmtree(OUT, ignore_errors=True)
    shutil.copytree(SRC, OUT, ignore=shutil.ignore_patterns("_metadata"))

    m = json.loads((OUT / "manifest.json").read_text())

    # Firefox runs MV3 backgrounds as event pages, not service workers.
    worker = m["background"].pop("service_worker")
    m["background"]["scripts"] = [worker]

    # Chrome-only: lets app.monarch.com message the extension (only used for
    # "website logged out" and "open popup"), plus the Web Store update URL.
    m.pop("externally_connectable", None)
    m.pop("update_url", None)

    # Firefox can't grant this one as optional, and without it the Cookie/Origin
    # rewrite for api.monarch.com never gets installed. It shows no install prompt.
    dnr = "declarativeNetRequestWithHostAccess"
    if dnr in m.get("optional_permissions", []):
        m["optional_permissions"].remove(dnr)
        m["permissions"].append(dnr)
    # "Log in to Monarch" calls permissions.request for ["cookies", <dnr>], and
    # Firefox rejects a request naming a non-optional permission, so the button
    # silently did nothing. Ask for cookies only; DNR is already granted.
    old = '["cookies","declarativeNetRequestWithHostAccess"]'
    hits = 0
    for js in OUT.rglob("*.js"):
        src = js.read_text()
        if old in src:
            hits += src.count(old)
            js.write_text(src.replace(old, '["cookies"]'))
    if not hits:
        sys.exit(f"patch.py: {old} not found; upstream changed, recheck the login permission request")

    # The Orders/Retailers links are built as chrome-extension://<runtime.id>/;
    # Firefox uses moz-extension://<per-install uuid>/, which getURL returns.
    ext_url = re.compile(r"chrome-extension://\$\{([\w$]+)\.runtime\.id\}/")
    hits = 0
    for js in OUT.rglob("*.js"):
        src, n = ext_url.subn(r'${\1.runtime.getURL("/")}', js.read_text())
        if n:
            hits += n
            js.write_text(src)
    if not hits:
        sys.exit("patch.py: chrome-extension:// link builder not found; upstream changed, recheck the Orders link")

    m["browser_specific_settings"] = {
        "gecko": {
            "id": GECKO_ID,
            "strict_min_version": MIN_FIREFOX,
            # Order details scraped from Amazon/Target go to Monarch; upstream
            # also reports usage to Segment and errors to Sentry. Firefox only
            # allows technicalAndInteraction as optional, but upstream code
            # doesn't check the toggle, so it's sent either way.
            "data_collection_permissions": {
                "required": ["financialAndPaymentInfo", "websiteContent"],
                "optional": ["technicalAndInteraction"],
            },
        }
    }

    if PATCH_LEVEL:
        m["version"] = f'{m["version"]}.{PATCH_LEVEL}'

    # Unofficial build: keep it from looking like Monarch's own listing.
    m["name"] = "Monarch Retail Sync (unofficial port)"  # AMO rejects "Firefox" in names
    m["description"] = (
        "Personal repackaging for this browser of Monarch Money's Retail Sync Chrome "
        "extension. Not affiliated with Monarch."
    )

    (OUT / "manifest.json").write_text(json.dumps(m, indent=2) + "\n")
    print("built", OUT, "version", m["version"])


if __name__ == "__main__":
    main()
