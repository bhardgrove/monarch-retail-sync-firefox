// Mirrors what the real extension does, against a local echo server:
//  - read the website's session cookie with cookies.get
//  - install a DNR modifyHeaders rule that sets Origin + Cookie on its own
//    fetches to the API host (api.monarch.com in the real thing)
//  - fetch a retailer page with credentials: "include" and rely on the
//    browser's own cookies (amazon.com / target.com in the real thing)
const BASE = "http://%s.probe.test:8080";
const url = (host, path) => BASE.replace("%s", host) + path;

(async () => {
  const r = {};
  try {
    const c = await browser.cookies.get({ url: url("app", "/"), name: "sess" });
    r.cookieRead = c && c.value;
    await browser.declarativeNetRequest.updateDynamicRules({
      removeRuleIds: [1],
      addRules: [{
        id: 1,
        priority: 1,
        action: {
          type: "modifyHeaders",
          requestHeaders: [
            { header: "Origin", operation: "set", value: url("app", "") },
            { header: "Cookie", operation: "set", value: `sess=${r.cookieRead}` },
          ],
        },
        condition: { urlFilter: "||api.probe.test", resourceTypes: ["xmlhttprequest"] },
      }],
    });
    r.rules = (await browser.declarativeNetRequest.getDynamicRules()).length;
    const api = await fetch(url("api", "/echo"), {
      method: "POST", credentials: "include",
      headers: { "content-type": "application/json" }, body: "{}",
    });
    r.api = await api.json();
    const shop = await fetch(url("shop", "/echo"), { credentials: "include" });
    r.shop = await shop.json();
  } catch (e) {
    r.error = String(e);
  }
  await fetch(url("report", "/report"), { method: "POST", body: JSON.stringify(r) });
})();
