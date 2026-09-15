"""Microsoft Graph email delivery."""

from __future__ import annotations

import base64
from typing import List, Optional

import httpx

from app.application.email_provider import EmailAttachment, EmailMessage, EmailProvider, EmailSendResult
from app.application.graph_access_token_provider import GraphTokenError, get_graph_access_token
from app.core.config import settings


class MicrosoftGraphEmailProvider(EmailProvider):
    def send(self, message: EmailMessage) -> EmailSendResult:
        if not settings.graph_sender_mailbox:
            return EmailSendResult(success=False, error_code="EMAIL_PROVIDER_AUTH_FAILED", error_message="Sender not configured.")
        try:
            token = get_graph_access_token()
        except GraphTokenError as exc:
            return EmailSendResult(success=False, error_code=exc.code, error_message=exc.message)

        content_type = "HTML" if message.html_body else "Text"
        body_content = message.html_body or message.body
        graph_message: dict = {
            "subject": message.subject,
            "body": {"contentType": content_type, "content": body_content},
            "toRecipients": [{"emailAddress": {"address": message.to}}],
        }
        if message.attachments:
            graph_message["attachments"] = []
            for att in message.attachments:
                graph_message["attachments"].append({
                    "@odata.type": "#microsoft.graph.fileAttachment",
                    "name": att.name,
                    "contentType": att.content_type,
                    "contentBytes": base64.b64encode(att.content).decode("ascii"),
                    "isInline": att.is_inline,
                    **({"contentId": att.content_id} if att.content_id else {}),
                })

        url = f"https://graph.microsoft.com/v1.0/users/{settings.graph_sender_mailbox}/sendMail"
        payload = {"message": graph_message, "saveToSentItems": settings.graph_save_to_sent_items}

        try:
            with httpx.Client(timeout=settings.graph_timeout_seconds) as client:
                resp = client.post(url, json=payload, headers={"Authorization": f"Bearer {token}"})
        except httpx.TimeoutException:
            return EmailSendResult(success=False, error_code="EMAIL_PROVIDER_UNAVAILABLE", error_message="Graph send timed out.")
        except httpx.HTTPError:
            return EmailSendResult(success=False, error_code="EMAIL_PROVIDER_UNAVAILABLE", error_message="Graph send failed.")

        if resp.status_code == 202:
            return EmailSendResult(success=True, provider_message_id=f"graph-{hash(message.subject) & 0xFFFFFFFF}")
        if resp.status_code == 429:
            return EmailSendResult(success=False, error_code="EMAIL_PROVIDER_RATE_LIMITED", error_message="Graph rate limited.")
        if resp.status_code in (401, 403):
            return EmailSendResult(success=False, error_code="EMAIL_PROVIDER_AUTH_FAILED", error_message="Graph authorization failed.")
        if resp.status_code >= 500:
            return EmailSendResult(success=False, error_code="EMAIL_PROVIDER_UNAVAILABLE", error_message="Graph server error.")
        return EmailSendResult(success=False, error_code="EMAIL_SEND_FAILED", error_message="Graph rejected message.")
