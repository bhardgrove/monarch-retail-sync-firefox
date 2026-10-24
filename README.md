# Monarch Retail Sync for Firefox (unofficial)

Monarch Money's [Retail Sync extension](https://help.monarch.com/hc/en-us/articles/36463599367188)
matches Amazon and Target orders to your Monarch transactions, but Monarch
only ships it for Chrome. These scripts turn the
[Chrome Web Store build](https://chromewebstore.google.com/detail/imfcckkmcklambpijbgcebggegggkgla)
into a Firefox add-on that you sign with your own free Mozilla developer account
and install in your own browser.

> **Not affiliated with Monarch Money.** This repo contains no Monarch code: the
> extension is downloaded from the Chrome Web Store when you build. Monarch's
> [terms](https://www.monarch.com/terms) restrict modifying their software;
> using this is your call. Please don't redistribute signed builds or list them
> on addons.mozilla.org. If you want Firefox support, ask Monarch for it.

## Requirements

- Linux or macOS with `bash`, `curl`, `python3` and Docker. The linter, signer
  and test browser all run in containers.
- A free [addons.mozilla.org](https://addons.mozilla.org) account. Signing is
  automatic and unlisted: the add-on is never published, and Mozilla just signs
  it so release Firefox will install it.
- Firefox 128 or newer.

## Build, sign, install

```sh
scripts/setup.sh     # once: choose an add-on id, save your AMO API key
scripts/fetch.sh     # download the current Chrome Web Store build into upstream/
test/run.sh          # optional: headless Firefox ESR tests (Docker)
scripts/sign.sh      # patch, lint, submit as unlisted, save dist/*-signed.xpi
```

`setup.sh` asks for:

- **An add-on id** in email form, such as `monarch-retail-sync@yourname`. It's
  saved to `local.env`, which isn't committed. Mozilla ties the id to the
  account that first signs it, so pick your own and keep it for future versions.
- **AMO API credentials** from <https://addons.mozilla.org/developers/addon/api/key/>.
  New accounts must set a display name and accept the developer agreement there
  first. The credentials are checked, then stored in `~/.config/amo/credentials`
  with mode 600.

Signing usually takes a few minutes. Open the `.xpi` in Firefox (drag it into a
window, or `about:addons` → gear → Install Add-on From File). Then click the
toolbar icon → **Log in to Monarch**, allow access to `api.monarch.com`, log in
on the tab that opens, and set up your retailers.

The add-on doesn't update itself. When Monarch releases a new version, run
`fetch.sh` and `sign.sh` again and install the new `.xpi` over the old one. To
re-sign the same upstream version with a different patch, bump `PATCH_LEVEL` in
`scripts/patch.py`. Mozilla never accepts the same version twice.

## What the port changes

The extension is built with [WXT](https://wxt.dev), which already uses
`browser.*` when it exists. So `scripts/patch.py` changes the manifest plus two
small JS rewrites. Each JS rewrite fails the build if its target string
disappears from a new upstream release.

| Change | Why |
| --- | --- |
| `background.service_worker` → `background.scripts` | Firefox runs MV3 backgrounds as event pages |
| `declarativeNetRequestWithHostAccess` optional → required | Firefox can't grant it as optional; without it the Cookie/Origin rewrite for `api.monarch.com` never gets installed. It shows no install prompt |
| Login permission request asks for `["cookies"]` only | Firefox rejects `permissions.request` for a non-optional permission, so **Log in to Monarch** silently did nothing |
| Orders/Retailers links use `runtime.getURL("/")` instead of `chrome-extension://${runtime.id}/` | Firefox extension URLs are `moz-extension://<per-install uuid>/` |
| Drop `externally_connectable`, `update_url`, `_metadata/` | Chrome-only. You lose "logging out on monarch.com logs out the extension"; use **Sign out** in the extension's settings instead |
| Add `browser_specific_settings.gecko` | Your add-on id, Firefox 128+, and a data-collection declaration |
| Rename and new description | Makes clear this isn't Monarch's own add-on (Mozilla also rejects "Firefox" in add-on names) |

**Data collection.** As in Chrome, order details from Amazon and Target go to
Monarch. Upstream also sends usage events to Segment and errors to Sentry, and
nothing in its code turns that off.

**Container tabs.** The extension reads cookies from the default container, so
log in to Monarch, Amazon and Target in normal tabs.

## Tests

`test/run.sh` builds `build/` and runs headless Firefox ESR in Docker:

- **Probe extension** (`test/probe/`): repeats the real extension's steps
  against a local echo server. It reads a site cookie with `cookies.get`, adds a
  DNR `modifyHeaders` rule that sets `Origin` and `Cookie` on its own fetches,
  and fetches a "retailer" with `credentials: "include"`. The checks confirm
  Firefox applies both headers and sends the retailer's first-party cookie.
- **Real build**:
  - Loads as a temporary add-on and checks the background starts.
  - Renders `popup.html` and `options.html`; screenshots go to `test/out/`.
  - Clicks **Log in to Monarch** for real and expects the API permission plus a
    `app.monarch.com/login` tab.
  - Grants the retailer permissions and fetches live Amazon, Target and Monarch
    endpoints from the extension's origin.
  - Fails if any `chrome-extension://` link is left in the build.

Logging in to Monarch and syncing real orders is manual. It has been confirmed
working with upstream 1.0.34.

## License

The scripts in this repo are MIT licensed (see [LICENSE](LICENSE)). The
extension they download is Monarch Money's and is not covered by it.
