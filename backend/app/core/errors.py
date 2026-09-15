from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.core.config import settings
from app.core.request_context import get_request_id

logger = logging.getLogger(__name__)


class APIError(Exception):
    def __init__(self, status_code: int, code: str, message: str, details: Any = None):
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details


async def api_error_handler(_request: Request, exc: APIError) -> JSONResponse:
    rid = get_request_id()
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
                "request_id": rid or None,
            }
        },
    )


async def database_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    rid = get_request_id()
    return JSONResponse(
        status_code=503,
        content={
            "error": {
                "code": "DATABASE_UNAVAILABLE",
                "message": "Database is temporarily unavailable.",
                "request_id": rid or None,
            }
        },
    )


async def generic_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    rid = get_request_id()
    if not settings.is_production:
        logger.exception(
            "Unhandled API error request_id=%s exc_type=%s",
            rid,
            type(exc).__name__,
        )
    if settings.is_production:
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "internal_error",
                    "message": "An unexpected error occurred.",
                    "request_id": rid or None,
                }
            },
        )
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "internal_error",
                "message": "An unexpected error occurred.",
                "request_id": rid or None,
            }
        },
    )


def _build_csp() -> str:
    origins = settings.cors_origin_list
    connect = " ".join(origins) + " https://login.microsoftonline.com https://graph.microsoft.com"
    return (
        "default-src 'self'; "
        f"connect-src 'self' {connect}; "
        "img-src 'self' data: blob:; "
        "style-src 'self' 'unsafe-inline'; "
        "script-src 'self'; "
        "frame-src 'self' https://login.microsoftonline.com; "
        "frame-ancestors 'none'; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    )


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(self), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = _build_csp()
        response.headers["X-Frame-Options"] = "DENY"
        if settings.is_production and settings.public_app_base_url.startswith("https://"):
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response
