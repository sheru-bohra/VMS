"""Lightweight rate limiting for public endpoints."""

from __future__ import annotations

from fastapi import Request

from app.application.rate_limit_store import get_rate_limit_store, hash_rate_limit_key
from app.core.config import settings
from app.core.errors import APIError
from app.infrastructure.database import SessionLocal


def get_client_address(request: Request) -> str:
    if settings.trust_proxy_headers:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _check(bucket: str, client_key: str, limit: int) -> None:
    store = get_rate_limit_store(SessionLocal)
    key = f"{bucket}:{client_key}"
    if not store.check_and_increment(key, limit, 60):
        raise APIError(429, "RATE_LIMITED", "Too many requests. Please try again shortly.")


def check_public_rate_limit(request: Request, bucket: str, limit: int) -> None:
    client = get_client_address(request)
    _check(bucket, hash_rate_limit_key(client), limit)


def check_registration_rate_limit(request: Request) -> None:
    check_public_rate_limit(request, "registration", settings.rate_limit_registration_per_minute)


def check_public_site_rate_limit(request: Request) -> None:
    check_public_rate_limit(request, "public_site", settings.rate_limit_public_per_minute)


def check_invitation_public_rate_limit(request: Request) -> None:
    check_public_rate_limit(request, "invitation_public", settings.rate_limit_invitation_per_minute)


def check_host_approval_rate_limit(request: Request) -> None:
    check_public_rate_limit(request, "host_approval", settings.rate_limit_host_approval_per_minute)


def check_ai_copilot_rate_limit(user_email: str) -> None:
    _check("ai_copilot", hash_rate_limit_key(user_email), settings.rate_limit_ai_copilot_per_minute)


def check_ai_insight_refresh_rate_limit(user_email: str) -> None:
    _check("ai_insight_refresh", hash_rate_limit_key(user_email), settings.rate_limit_ai_insight_refresh_per_minute)


def check_direct_owner_login_rate_limit(request: Request, email: str) -> None:
    check_vms_native_login_rate_limit(request, email)


def check_vms_native_login_rate_limit(request: Request, email: str) -> None:
    client = get_client_address(request)
    limit = settings.rate_limit_vms_native_login_per_minute
    _check("vms_native_login_email", hash_rate_limit_key(email.lower()), limit)
    _check("vms_native_login_ip", hash_rate_limit_key(client), limit)


def check_vms_native_password_change_rate_limit(request: Request, email: str) -> None:
    client = get_client_address(request)
    limit = settings.rate_limit_vms_native_password_change_per_minute
    _check("vms_native_password_email", hash_rate_limit_key(email.lower()), limit)
    _check("vms_native_password_ip", hash_rate_limit_key(client), limit)
