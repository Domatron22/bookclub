# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Domatron22
"""Google sign-in via OpenID Connect.

Authlib does the protocol work: discovery, the `state`/`nonce` round trip,
and ID-token signature validation against Google's JWKS. PKCE is opt-in and is
turned on below. What lives here is the configuration and the
deployment-specific detail of working out which redirect URI to hand Google.

Sign-in is optional. With no client credentials configured the app runs exactly
as before and the Google buttons are hidden, so self-hosters are never forced
to create a Google Cloud project just to use Coverbound.
"""
import os
from urllib.parse import urlparse

from authlib.integrations.starlette_client import OAuth
from fastapi import Request

GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"

# `openid email profile` is the minimum that yields a stable subject id, an
# address to show the user, and a display name to prefill their profile.
GOOGLE_SCOPES = "openid email profile"


def _env(name: str) -> str:
    return (os.getenv(name) or "").strip()


# Resolved once, at import, so `google_enabled()` can never disagree with
# whether the client below actually got registered — a template showing a
# button for an unregistered client would 500 on click.
_ENABLED = bool(_env("GOOGLE_CLIENT_ID") and _env("GOOGLE_CLIENT_SECRET"))


def google_enabled() -> bool:
    """True when this deployment has Google credentials configured.

    Fixed at startup: changing the environment needs a restart, same as every
    other setting in coverbound.env.
    """
    return _ENABLED


oauth = OAuth()

if _ENABLED:
    oauth.register(
        name="google",
        client_id=_env("GOOGLE_CLIENT_ID"),
        client_secret=_env("GOOGLE_CLIENT_SECRET"),
        server_metadata_url=GOOGLE_DISCOVERY_URL,
        client_kwargs={
            "scope": GOOGLE_SCOPES,
            # Not on by default in Authlib. We're a confidential client, so the
            # secret already binds the exchange, but PKCE additionally stops a
            # leaked authorization code (proxy logs, Referer, shoulder-surfed
            # redirect) from being redeemed by anyone else.
            "code_challenge_method": "S256",
        },
    )


def redirect_uri(request: Request) -> str:
    """The callback URL to send Google, which must match a registered URI exactly.

    Behind a reverse proxy the app usually sees plain HTTP on an internal host,
    so deriving this from the request alone produces `http://127.0.0.1:8000/...`
    — which Google rejects. `PUBLIC_BASE_URL` overrides it with the address
    users actually type.
    """
    base = _env("PUBLIC_BASE_URL")
    if base:
        return f"{base.rstrip('/')}/auth/google/callback"
    return str(request.url_for("google_callback"))


def is_safe_next(target: str) -> bool:
    """Whether `target` is a same-site path we're willing to redirect to.

    Anything absolute, protocol-relative, or pointing at another host is
    rejected: a `next=` parameter is attacker-supplied, and an open redirect off
    the back of a login page is a ready-made phishing tool.
    """
    if not target or not target.startswith("/") or target.startswith("//"):
        return False
    parsed = urlparse(target)
    return not parsed.scheme and not parsed.netloc


def safe_next(target: "str | None", fallback: str = "/") -> str:
    """The redirect target if it is a safe same-site path, else `fallback`."""
    return target if target and is_safe_next(target) else fallback
