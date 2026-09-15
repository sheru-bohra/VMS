"""Canonical public self-registration URLs (permanent location tokens)."""

from __future__ import annotations

from urllib.parse import urljoin

from app.core.config import settings


def build_registration_public_url(token: str) -> str:
    base = settings.public_app_origin.rstrip("/")
    path = f"/visit/register/{token}"
    return urljoin(f"{base}/", path.lstrip("/"))


def is_localhost_public_url(url: str) -> bool:
    lowered = url.lower()
    return "localhost" in lowered or "127.0.0.1" in lowered
