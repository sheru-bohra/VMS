"""Backward-compatible aliases for owner-only direct auth (superseded by vms_native_auth_service)."""

from app.application.vms_native_auth_service import (
    VMS_NATIVE_AUTH_PROVIDER,
    VmsNativeAuthError,
    authenticate_vms_native_login,
    authenticate_vms_native_token,
    invalidate_vms_native_sessions,
    is_vms_native_token,
    issue_vms_native_token,
    provision_owner_password_if_needed,
)

DIRECT_OWNER_AUTH_PROVIDER = VMS_NATIVE_AUTH_PROVIDER
DIRECT_OWNER_TOKEN_ISSUER = "vms-direct-owner"


class DirectOwnerAuthError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 401):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def is_direct_owner_token(token: str) -> bool:
    return is_vms_native_token(token)


def issue_direct_owner_token(user):
    return issue_vms_native_token(user)


def authenticate_direct_owner_token(db, token: str):
    try:
        return authenticate_vms_native_token(db, token)
    except VmsNativeAuthError as exc:
        raise DirectOwnerAuthError(exc.code, exc.message, exc.status_code)


def authenticate_direct_owner_login(db, email: str, password: str, request):
    token, expires_in, _ = authenticate_vms_native_login(db, email, password, request)
    return token, expires_in


def invalidate_direct_owner_sessions(user):
    return invalidate_vms_native_sessions(user)


def ensure_owner_direct_auth(db, owner):
    from app.application.vms_native_auth_service import ensure_vms_native_auth

    return ensure_vms_native_auth(db, owner)


__all__ = [
    "DIRECT_OWNER_AUTH_PROVIDER",
    "DIRECT_OWNER_TOKEN_ISSUER",
    "DirectOwnerAuthError",
    "authenticate_direct_owner_login",
    "authenticate_direct_owner_token",
    "ensure_owner_direct_auth",
    "invalidate_direct_owner_sessions",
    "is_direct_owner_token",
    "issue_direct_owner_token",
    "provision_owner_password_if_needed",
]
