# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Domatron22
"""Auth regression harness: sessions, Google sign-in, linking, logout.

A real OAuth round trip needs live Google credentials, so this mints the same
signed session cookie the callback would have written and exercises everything
downstream of it — plus the session-security properties that don't involve
Google at all.

Run against a throwaway database, not one you care about: it creates accounts.

    DATABASE_URL=sqlite:////tmp/auth-test.db .venv/bin/python scripts/seed_demo.py --reset
    SECRET_KEY=... GOOGLE_CLIENT_ID=x GOOGLE_CLIENT_SECRET=y \
        .venv/bin/uvicorn app.main:app --port 8011 &
    BASE=http://127.0.0.1:8011 SECRET_KEY=... .venv/bin/python scripts/check_auth.py
"""
import base64, json, os, sys
import requests
from itsdangerous import TimestampSigner

B = os.environ.get("BASE", "http://127.0.0.1:8011")
SECRET = os.environ.get("SECRET_KEY")
if not SECRET:
    sys.exit("Set SECRET_KEY to the same value the server under test is using.")
HOST = B.split("//", 1)[1].split(":")[0]
signer = TimestampSigner(SECRET)

def session_cookie(data: dict) -> str:
    raw = base64.b64encode(json.dumps(data).encode("utf-8"))
    return signer.sign(raw).decode("utf-8")

def set_session(sess: requests.Session, value: str) -> None:
    """Install a session cookie scoped like a real one.

    Without an explicit domain, requests stores it under "" — and a deletion
    the server scopes to the real host then fails to match, so the jar keeps
    replaying a cookie the server has already revoked.
    """
    sess.cookies.set("session", value, domain=HOST, path="/")


def read_session(cookie: str) -> dict:
    raw = signer.unsign(cookie, max_age=86400)
    return json.loads(base64.b64decode(raw))

results = []
def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  — {detail}" if detail else ""))

PENDING = {
    "pending_google": {
        "sub": "google-sub-abc123", "email": "reader@example.com",
        "email_verified": True, "name": "Ada Reader",
        "picture": "https://example.com/a.png", "next": "/",
    }
}

# 0. The pre-3.1 identity cookie must no longer authenticate anyone.
s0 = requests.Session()
s0.cookies.set("coverbound_user_id", "1", domain=HOST, path="/")
r = s0.get(f"{B}/profile/settings", allow_redirects=False)
check("legacy id cookie grants nothing", r.status_code in (303, 401), f"status={r.status_code}")

# 1. The username picker renders from pending state
s = requests.Session()
set_session(s, session_cookie(PENDING))
r = s.get(f"{B}/auth/google/finish")
check("finish page renders", r.status_code == 200, f"status={r.status_code}")
check("prefills a suggested username", 'value="reader"' in r.text, "expected local-part 'reader'")
check("shows the Google address", "reader@example.com" in r.text)

# 2. Rejects a bad username without creating anything
s2 = requests.Session(); set_session(s2, session_cookie(PENDING))
r = s2.post(f"{B}/auth/google/finish", data={"username": "no"}, allow_redirects=False)
check("rejects too-short username", r.status_code == 400, f"status={r.status_code}")

# 3. Creates the account and logs in
s3 = requests.Session(); set_session(s3, session_cookie(PENDING))
r = s3.post(f"{B}/auth/google/finish", data={"username": "adareader"}, allow_redirects=False)
check("creates account", r.status_code == 303, f"status={r.status_code}")
new_cookie = r.cookies.get("session")
check("issues a signed session", bool(new_cookie))
if new_cookie:
    sess = read_session(new_cookie)
    check("session holds uid, not pending state",
          "uid" in sess and "pending_google" not in sess, str(sess))

# 4. That session can reach an authenticated page
s4 = requests.Session(); set_session(s4, new_cookie)
r = s4.get(f"{B}/profile/settings")
check("logged in via session", r.status_code == 200, f"status={r.status_code}")
check("settings shows Google connected", "Connected" in r.text and "reader@example.com" in r.text)
check("no secret-reveal widget for Google-only account",
      "Click to reveal" not in r.text)
check("explains there is no account secret",
      "no account secret" in r.text)

# 5. Same Google sub can't sign up twice
s5 = requests.Session(); set_session(s5, session_cookie(PENDING))
r = s5.post(f"{B}/auth/google/finish", data={"username": "adareader2"}, allow_redirects=False)
check("second signup with same sub rejected", r.status_code == 409, f"status={r.status_code}")

# 6. Unlinking a Google-only account mints a secret instead of locking them out
r = s4.post(f"{B}/auth/google/unlink", allow_redirects=False)
check("unlink redirects to the one-time reveal",
      r.status_code == 303 and r.headers.get("location") == "/auth/register/success",
      f"{r.status_code} {r.headers.get('location')}")
r = s4.get(f"{B}/auth/register/success")
check("reveal page shown after unlink", r.status_code == 200, f"status={r.status_code}")
check("reveal page uses the unlink heading", "Google disconnected" in r.text)

# 7. Login with a username that now signs in by secret only
r = s4.get(f"{B}/profile/settings")
check("account still reachable after unlink", r.status_code == 200, f"status={r.status_code}")
check("secret widget returns", "Click to reveal" in r.text)

# 8. Logout clears identity
r = s4.post(f"{B}/auth/logout", allow_redirects=False)
check("logout redirects", r.status_code == 303, f"status={r.status_code}")
r = s4.get(f"{B}/profile/settings", allow_redirects=False)
check("logged out cannot reach settings", r.status_code in (303, 401), f"status={r.status_code}")

# 9. A tampered session cookie is rejected
s6 = requests.Session()
bad = session_cookie({"uid": 1})
set_session(s6, bad[:-4] + "AAAA")
r = s6.get(f"{B}/profile/settings", allow_redirects=False)
check("tampered session rejected", r.status_code in (303, 401), f"status={r.status_code}")

# 10. A validly-signed session naming a deleted user fails closed
s7 = requests.Session(); set_session(s7, session_cookie({"uid": 999999}))
r = s7.get(f"{B}/profile/settings", allow_redirects=False)
check("unknown uid rejected", r.status_code in (303, 401), f"status={r.status_code}")

failed = [r for r in results if not r[1]]
print(f"\n{len(results) - len(failed)}/{len(results)} passed")
sys.exit(1 if failed else 0)
