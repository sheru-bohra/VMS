"""Approval actor context for admin and host-link decisions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.application.auth_service import AuthContext
from app.domain.enums import ApprovalActorType


@dataclass
class ApprovalActor:
    actor_type: str
    actor_user_id: Optional[int] = None
    actor_host_id: Optional[int] = None
    actor_email: Optional[str] = None
    actor_role: Optional[str] = None
    actor_name: Optional[str] = None


def actor_from_auth(ctx: AuthContext) -> ApprovalActor:
    return ApprovalActor(
        actor_type=ApprovalActorType.ADMIN_USER.value,
        actor_user_id=ctx.user_id,
        actor_email=ctx.email,
        actor_role=ctx.role.value,
        actor_name=ctx.display_name,
    )


def actor_from_host(host_id: int, host_email: Optional[str], host_name: str) -> ApprovalActor:
    return ApprovalActor(
        actor_type=ApprovalActorType.HOST_LINK.value,
        actor_host_id=host_id,
        actor_email=host_email,
        actor_name=host_name,
    )
