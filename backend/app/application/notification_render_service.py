"""Render notification content with HTML escaping."""

from __future__ import annotations

import html
import json
from typing import Any, Dict, List, Optional, Tuple

from app.application.data_encryption_service import decrypt_value, EncryptionError
from app.application.email_provider import EmailAttachment
from app.application.notification_templates import TEMPLATE_RENDERERS, TEMPLATE_HTML_RENDERERS
from app.domain.models import Notification


def _prepare_payload(notification: Notification) -> Dict[str, Any]:
    payload = json.loads(notification.payload_json or "{}")
    if payload.get("approval_url_enc"):
        try:
            payload["approval_url"] = decrypt_value(payload["approval_url_enc"])
        except EncryptionError:
            payload["approval_url"] = None
    return payload


def render_notification_email(notification: Notification) -> Tuple[str, str, Optional[str], List[EmailAttachment]]:
    payload = _prepare_payload(notification)
    key = notification.template_key or ""
    renderer = TEMPLATE_RENDERERS.get(key)
    html_renderer = TEMPLATE_HTML_RENDERERS.get(key)
    if not renderer:
        subject = notification.subject or "VMS Notification"
        body = notification.body_preview or ""
        return subject, body, None, []
    subject, body = renderer(payload)
    html_body = html_renderer(payload) if html_renderer else None
    attachments: List[EmailAttachment] = []
    if payload.get("qr_png_base64"):
        import base64
        attachments.append(
            EmailAttachment(
                name="visitor-invitation-qr.png",
                content=base64.b64decode(payload["qr_png_base64"]),
                content_type="image/png",
                is_inline=True,
                content_id="visitor_qr",
            )
        )
    return subject, body, html_body, attachments
