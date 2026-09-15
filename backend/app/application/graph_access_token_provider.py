"""Microsoft Graph app-only access token management."""

from __future__ import annotations

import time
from typing import Optional

import httpx

from app.core.config import settings


class GraphTokenError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


_cached_token: Optional[str] = None
_cached_expiry: float = 0.0


def get_graph_access_token() -> str:
    global _cached_token, _cached_expiry
    now = time.time()
    if _cached_token and now < _cached_expiry - 60:
        return _cached_token

    tenant = settings.graph_tenant_id or settings.entra_tenant_id
    if not tenant or not settings.graph_client_id or not settings.graph_client_secret:
        raise GraphTokenError("EMAIL_PROVIDER_AUTH_FAILED", "Graph credentials are not configured.")

    url = f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
    data = {
        "client_id": settings.graph_client_id,
        "client_secret": settings.graph_client_secret,
        "scope": "https://graph.microsoft.com/.default",
        "grant_type": "client_credentials",
    }
    try:
        with httpx.Client(timeout=settings.graph_timeout_seconds) as client:
            resp = client.post(url, data=data)
    except httpx.TimeoutException:
        raise GraphTokenError("EMAIL_PROVIDER_UNAVAILABLE", "Graph token request timed out.")
    except httpx.HTTPError:
        raise GraphTokenError("EMAIL_PROVIDER_UNAVAILABLE", "Graph token request failed.")

    if resp.status_code != 200:
        raise GraphTokenError("EMAIL_PROVIDER_AUTH_FAILED", "Graph authentication failed.")

    body = resp.json()
    token = body.get("access_token")
    if not token:
        raise GraphTokenError("EMAIL_PROVIDER_AUTH_FAILED", "Graph token response invalid.")
    expires_in = int(body.get("expires_in", 3600))
    _cached_token = token
    _cached_expiry = now + expires_in
    return token


def clear_graph_token_cache() -> None:
    global _cached_token, _cached_expiry
    _cached_token = None
    _cached_expiry = 0.0
