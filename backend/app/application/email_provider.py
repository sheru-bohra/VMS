"""Email provider abstraction."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class EmailAttachment:
    name: str
    content: bytes
    content_type: str
    is_inline: bool = False
    content_id: Optional[str] = None


@dataclass
class EmailMessage:
    to: str
    subject: str
    body: str
    html_body: Optional[str] = None
    attachments: Optional[List[EmailAttachment]] = None


@dataclass
class EmailSendResult:
    success: bool
    provider_message_id: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None


class EmailProvider(ABC):
    @abstractmethod
    def send(self, message: EmailMessage) -> EmailSendResult:
        ...


class DevOutboxEmailProvider(EmailProvider):
    """Captures email in-process; does not send externally."""

    def send(self, message: EmailMessage) -> EmailSendResult:
        return EmailSendResult(success=True, provider_message_id=f"dev-{hash(message.subject) & 0xFFFFFFFF}")


def get_email_provider() -> EmailProvider:
    from app.core.config import settings

    if settings.email_provider == "dev_outbox":
        return DevOutboxEmailProvider()
    if settings.email_provider == "ms_graph":
        raise RuntimeError(
            "EMAIL_PROVIDER=ms_graph is not supported. Microsoft Graph is not used by VMS."
        )
    raise RuntimeError(f"Unsupported email provider: {settings.email_provider}")
