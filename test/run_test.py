#!/usr/bin/env python3
"""Runs inside the test container (see test/run.sh).

1. Probe: does Firefox apply the extension's Cookie/Origin DNR rewrite to the
   extension's own fetches, and send site cookies on credentials:"include"?
2. Real build: loads as a temporary add-on, background starts without errors,
   popup and options pages render, optional host permissions can be granted.
"""
import http.server
import json
import os
import sys
import threading
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service

OUT = Path("/out")
REPORT = {}


class Echo(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, extra=()):
        self.send_response(code)
        for k, v in extra:
            self.send_header(k, v)
        self.send_header("content-type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        host = self.headers.get("host", "").split(".")[0]
        if self.path == "/setcookie":
            self._send(200, b"{}", [("set-cookie", f"sess={host}-first-party; Path=/")])
        else:
            self._send(200, json.dumps({k.lower(): v for k, v in self.headers.items()}).encode())

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("content-length", 0)))
        if self.path == "/report":
            REPORT.update(json.loads(body))
        self.do_GET()


def driver():
    o = Options()
    o.binary_location = "/usr/bin/firefox-esr"
    o.add_argument("-headless")
    o.add_argument("-remote-allow-system-access")
    for k, v in {
        "extensions.webextOptionalPermissionPrompts": False,
        "devtools.console.stdout.chrome": True,
        "devtools.console.stdout.content": True,
    }.items():
        o.set_preference(k, v)
    d = webdriver.Firefox(options=o, service=Service("/usr/local/bin/geckodriver", log_output="/out/geckodriver.log"))
    d.set_window_size(1280, 900)
    return d


def ext_uuid(d, ext_id):
    with d.context(d.CONTEXT_CHROME):
        return json.loads(d.execute_script(
            'return Services.prefs.getStringPref("extensions.webextensions.uuids")'))[ext_id]


def probe():
    d = driver()
    try:
        # The user has visited both sites, so they hold first-party cookies.
        for h in ("app", "shop"):
            d.get(f"http://{h}.probe.test:8080/setcookie")
        d.install_addon("/work/test/probe", temporary=True)
        for _ in range(50):
            if REPORT:
                break
            time.sleep(0.2)
    finally:
        d.quit()
    r = REPORT
    api = r.get("api", {})
    checks = {
        "cookies.get reads site cookie": r.get("cookieRead") == "app-first-party",
        "DNR rule installed": r.get("rules") == 1,
        "DNR sets Origin on own fetch": api.get("origin") == "http://app.probe.test:8080",
        "DNR sets Cookie on own fetch": api.get("cookie") == "sess=app-first-party",
        "retailer fetch sends site cookie": r.get("shop", {}).get("cookie") == "sess=shop-first-party",
    }
    return r, checks


def real():
    d = driver()
    res = {}
    try:
        ext_id = d.install_addon("/work/build", temporary=True)
        uuid = ext_uuid(d, ext_id)
        base = f"moz-extension://{uuid}"
        time.sleep(3)  # let the background script start and run its init
        for page in ("popup", "options"):
            d.get(f"{base}/{page}.html")
            time.sleep(3)
            d.save_screenshot(str(OUT / f"{page}.png"))
            res[f"{page} text"] = d.find_element("tag name", "body").text[:400]
        # Click "Log in to Monarch" for real (prompts auto-accept via the
        # webextOptionalPermissionPrompts pref): it must get the API permission
        # and then move on to Monarch's login.
        before = set(d.window_handles)
        d.find_element("xpath", "//button[normalize-space()='Log in to Monarch']").click()
        time.sleep(5)
        res["login click perms"] = d.execute_async_script("""
            const done = arguments[arguments.length - 1];
            browser.permissions.getAll().then(done, e => done(String(e)));
        """)
        tabs = []
        for h in set(d.window_handles) - before:
            d.switch_to.window(h)
            tabs.append(d.current_url[:120])
        d.switch_to.window(sorted(before)[0])
        res["login click new tabs"] = tabs
        d.save_screenshot(str(OUT / "after-login-click.png"))
        res["login click page text"] = d.find_element("tag name", "body").text[:300]
        # Grant the rest of the optional permissions the way the retailer
        # prompts' "Allow" button does.
        with d.context(d.CONTEXT_CHROME):
            d.execute_async_script("""
                const done = arguments[arguments.length - 1];
                const {ExtensionParent} = ChromeUtils.importESModule("resource://gre/modules/ExtensionParent.sys.mjs");
                const {ExtensionPermissions} = ChromeUtils.importESModule("resource://gre/modules/ExtensionPermissions.sys.mjs");
                const ext = ExtensionParent.GlobalManager.getExtension(arguments[0]);
                ExtensionPermissions.add(arguments[0], {permissions: ["cookies"], origins: ext.manifest.optional_host_permissions}, ext)
                  .then(() => done(true), e => done(String(e)));
            """, ext_id)
        # Live network from the extension's origin: no CORS failures, real servers answer.
        res["granted + live fetches"] = d.execute_async_script("""
            const done = arguments[arguments.length - 1];
            (async () => {
              const r = {perms: await browser.permissions.getAll(),
                         dnr: typeof browser.declarativeNetRequest?.updateDynamicRules,
                         cookiesApi: typeof browser.cookies?.get};
              for (const [k, u, init] of [
                ["amazon", "https://www.amazon.com/gp/css/order-history?disableCsd=no-js", {credentials: "include"}],
                ["target", "https://www.target.com/orders", {credentials: "include"}],
                ["monarch", "https://api.monarch.com/graphql", {method: "POST", credentials: "include",
                  headers: {"content-type": "application/json"}, body: '{"query":"{ me { id } }"}'}],
              ]) {
                try { const x = await fetch(u, init); r[k] = `${x.status} ${x.url}`.slice(0, 160); }
                catch (e) { r[k] = String(e); }
              }
              return r;
            })().then(done, e => done(String(e)));
        """)
        with d.context(d.CONTEXT_CHROME):
            res["background loaded"] = d.execute_script("""
                const {ExtensionParent} = ChromeUtils.importESModule("resource://gre/modules/ExtensionParent.sys.mjs");
                const ext = ExtensionParent.GlobalManager.getExtension(arguments[0]);
                return !!(ext && ext.backgroundState);
            """, ext_id)
    finally:
        d.quit()
    return res


def main():
    srv = http.server.ThreadingHTTPServer(("0.0.0.0", 8080), Echo)
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    r, checks = probe()
    print("== probe report\n" + json.dumps(r, indent=1))
    print("== probe checks")
    for k, ok in checks.items():
        print(("PASS " if ok else "FAIL ") + k)

    # Hand-built chrome-extension:// links can't open in Firefox.
    chrome_links = [str(p) for p in Path("/work/build").rglob("*.js") if "chrome-extension://" in p.read_text()]
    checks["no chrome-extension:// links in build"] = not chrome_links
    print(("PASS " if not chrome_links else f"FAIL {chrome_links} ") + "no chrome-extension:// links in build")

    print("== real build")
    res = real()
    print(json.dumps(res, indent=1))
    login_ok = any(t.startswith("https://app.monarch.com/login") for t in res.get("login click new tabs", []))
    print(("PASS " if login_ok else "FAIL ") + "Log in to Monarch opens Monarch login")
    sys.exit(0 if all(checks.values()) and login_ok else 1)


if __name__ == "__main__":
    main()
