"""Microsoft Entra ID token validation (OIDC — authentication only, no Graph)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import jwt
from jwt import PyJWKClient

from app.core.config import settings


class EntraTokenError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 401):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


_jwks_client: Optional[PyJWKClient] = None


def _issuer() -> str:
    return f"https://login.microsoftonline.com/{settings.entra_tenant_id}/v2.0"


def _jwks_url() -> str:
    return f"https://login.microsoftonline.com/{settings.entra_tenant_id}/discovery/v2.0/keys"


def _get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = PyJWKClient(_jwks_url(), cache_keys=True, lifespan=3600)
    return _jwks_client


def _configured_audiences() -> List[str]:
    audiences: List[str] = []
    if settings.entra_client_id:
        audiences.append(settings.entra_client_id)
    if settings.entra_api_audience and settings.entra_api_audience not in audiences:
        audiences.append(settings.entra_api_audience)
    return audiences


def _entra_configured() -> bool:
    return bool(settings.entra_tenant_id and (settings.entra_client_id or settings.entra_api_audience))


def validate_entra_id_token(token: str) -> Dict[str, Any]:
    """Validate a Microsoft Entra ID token (openid/profile/email OIDC flow)."""
    if not _entra_configured():
        raise EntraTokenError("AUTH_CONFIG_MISSING", "Entra authentication is not configured.", 503)

    audiences = _configured_audiences()
    if not audiences:
        raise EntraTokenError("AUTH_CONFIG_MISSING", "ENTRA_CLIENT_ID is not configured.", 503)

    try:
        signing_key = _get_jwks_client().get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=audiences,
            issuer=_issuer(),
            leeway=settings.entra_clock_skew_seconds,
            options={"require": ["exp", "iss", "aud", "sub"]},
        )
    except jwt.ExpiredSignatureError:
        raise EntraTokenError("AUTH_TOKEN_INVALID", "Authentication token has expired.")
    except jwt.InvalidTokenError:
        raise EntraTokenError("AUTH_TOKEN_INVALID", "Authentication token is invalid.")

    tid = claims.get("tid")
    if tid != settings.entra_tenant_id:
        raise EntraTokenError(
            "AUTH_WRONG_TENANT",
            "This Microsoft account does not belong to an authorized organization.",
        )

    allowed_clients = settings.entra_allowed_client_id_list
    if allowed_clients:
        azp = claims.get("azp") or claims.get("appid")
        if azp not in allowed_clients:
            raise EntraTokenError("AUTH_TOKEN_INVALID", "Token client application is not authorized.")

    oid = claims.get("oid") or claims.get("sub")
    if not oid:
        raise EntraTokenError("AUTH_TOKEN_INVALID", "Token is missing object identifier.")

    if not claims.get("oid"):
        claims = dict(claims)
        claims["oid"] = oid

    return claims


def validate_entra_access_token(token: str) -> Dict[str, Any]:
    """Backward-compatible alias — validates Entra ID tokens for API authentication."""
    return validate_entra_id_token(token)
