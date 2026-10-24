#!/usr/bin/env bash
# One-time setup before signing; run it in a terminal (it prompts for secrets).
#  1. Picks your add-on id and saves it to local.env.
#  2. Saves AMO API credentials to ~/.config/amo/credentials after checking them.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "== Add-on id"
echo "Any unique email-style id, e.g. monarch-retail-sync@<your-domain-or-username>."
echo "Keep it forever: AMO ties it to your account and later versions must reuse it."
read -rp "Add-on id: " ID
[[ $ID =~ ^[A-Za-z0-9._+-]+@[A-Za-z0-9._-]+$ ]] || { echo "not an email-style id"; exit 1; }
printf '# Per-user settings, not committed. See README.\nGECKO_ID=%s\n' "$ID" > local.env
echo "saved local.env"

echo
echo "== addons.mozilla.org"
echo "Get credentials at https://addons.mozilla.org/developers/addon/api/key/"
read -rp  "JWT issuer (user:...): " ISS
read -rsp "JWT secret (hidden): " SEC; echo

ok=$(AMO_ISS="$ISS" AMO_SEC="$SEC" python3 -I - <<'EOF'
import base64, hashlib, hmac, json, os, time, urllib.request, uuid
b64 = lambda b: base64.urlsafe_b64encode(b).rstrip(b"=")
now = int(time.time())
head = b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
body = b64(json.dumps({"iss": os.environ["AMO_ISS"], "jti": str(uuid.uuid4()), "iat": now, "exp": now + 60}).encode())
sig = b64(hmac.new(os.environ["AMO_SEC"].encode(), head + b"." + body, hashlib.sha256).digest())
req = urllib.request.Request("https://addons.mozilla.org/api/v5/accounts/profile/",
                             headers={"Authorization": "JWT " + (head + b"." + body + b"." + sig).decode()})
try:
    print(json.load(urllib.request.urlopen(req)).get("name") or "ok")
except Exception as e:
    print("FAIL", e)
EOF
)
case $ok in FAIL*) echo "AMO rejected the credentials: $ok"; exit 1 ;; esac
echo "AMO credentials work (account: $ok)"

mkdir -p ~/.config/amo
( umask 077; printf 'AMO_JWT_ISSUER=%s\nAMO_JWT_SECRET=%s\n' "$ISS" "$SEC" > ~/.config/amo/credentials )
echo "saved ~/.config/amo/credentials"
echo
echo "Done. Next: scripts/fetch.sh, test/run.sh, scripts/sign.sh"
