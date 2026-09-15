"""VMS Copilot orchestration — intent, context, provider, audit."""

from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.application.ai_context_gateway import AIContextError, build_context_for_intent
from app.application.ai_data_redaction_service import redact_question
from app.application.ai_intent_service import (
    CopilotIntent,
    MANAGEMENT_INTENTS,
    classify_intent,
)
from app.application.audit_service import AuditService
from app.application.auth_service import AuthContext
from app.application.dev_mock_ai_provider import get_ai_provider
from app.core.config import settings
from app.domain.enums import AdminRole, Permission, role_has_permission
from app.domain.models import AIInteraction, AISession


class CopilotError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def get_suggested_questions(ctx: AuthContext) -> List[str]:
    operational = [
        "Who is onsite right now?",
        "Which approvals are waiting?",
        "Which visitors are overstaying?",
        "Which contractors need compliance attention?",
    ]
    security = [
        "What needs security attention?",
        "Who is waiting for security review?",
        "Is an emergency active?",
    ]
    management = [
        "Compare visitor activity across locations",
        "What changed this week?",
        "Where are approval delays highest?",
        "What needs attention right now?",
    ]
    if role_has_permission(ctx.role, Permission.AI_MANAGEMENT_READ):
        return management + operational
    if ctx.role == AdminRole.SECURITY:
        return security + ["Who is onsite right now?", "Which approved visitors are expected next?"]
    return operational


def process_copilot_query(
    db: Session,
    ctx: AuthContext,
    question: str,
    location_id: Optional[int] = None,
    session_id: Optional[int] = None,
) -> Dict[str, Any]:
    if not settings.ai_enabled:
        raise CopilotError("ai_disabled", "AI assistance is currently disabled.", 503)
    if not role_has_permission(ctx.role, Permission.AI_COPILOT_USE):
        raise CopilotError("forbidden", "Permission denied.", 403)
    if not role_has_permission(ctx.role, Permission.AI_OPERATIONAL_READ):
        raise CopilotError("forbidden", "Permission denied.", 403)

    q = (question or "").strip()
    if not q:
        raise CopilotError("empty_question", "Please enter a question.")
    if len(q) > settings.ai_max_query_length:
        raise CopilotError("query_too_long", f"Maximum query length is {settings.ai_max_query_length} characters.")

    intent, unsupported_msg = classify_intent(q)
    start = time.monotonic()

    if intent == CopilotIntent.UNSUPPORTED:
        response = {
            "answer": unsupported_msg or "VMS Copilot only has access to visitor-management information.",
            "summary": unsupported_msg or "",
            "denied": False,
            "limitations": ["AI-generated operational assistance. Verify important decisions in VMS."],
        }
        _record_interaction(db, ctx, session_id, intent.value, location_id, q, response, "COMPLETED", start)
        AuditService(db).record(
            action="AI_QUERY_EXECUTED", entity_type="ai_copilot", entity_id="query",
            actor_id=ctx.user_id, actor_email=ctx.email,
            metadata={"intent": intent.value, "status": "unsupported"},
        )
        db.commit()
        return {"intent": intent.value, "response": response, "provider": settings.ai_provider}

    if intent in MANAGEMENT_INTENTS or intent == CopilotIntent.MANAGEMENT_SUMMARY:
        if not role_has_permission(ctx.role, Permission.AI_MANAGEMENT_READ):
            response = {
                "answer": "You don't have access to management analytics.",
                "summary": "Request outside authorized scope.",
                "denied": True,
                "limitations": ["AI-generated operational assistance. Verify important decisions in VMS."],
            }
            _record_interaction(db, ctx, session_id, intent.value, location_id, q, response, "DENIED", start)
            AuditService(db).record(action="AI_QUERY_DENIED", entity_type="ai_copilot", entity_id="query",
                                     actor_id=ctx.user_id, actor_email=ctx.email, metadata={"intent": intent.value})
            db.commit()
            return {"intent": intent.value, "response": response, "provider": settings.ai_provider}

    # Cross-location probe in question for scoped users
    if ctx.role in (AdminRole.SITE_ADMIN, AdminRole.SECURITY):
        cross_markers = ["mumbai", "delhi", "all location", "all offices", "across india", "every location", "compare"]
        if any(m in q.lower() for m in cross_markers) and intent in MANAGEMENT_INTENTS:
            response = {
                "answer": "You don't have access to management analytics.",
                "summary": "Request outside authorized scope.",
                "denied": True,
            }
            _record_interaction(db, ctx, session_id, intent.value, location_id, q, response, "DENIED", start)
            AuditService(db).record(action="AI_QUERY_DENIED", entity_type="ai_copilot", entity_id="query",
                                     actor_id=ctx.user_id, actor_email=ctx.email, metadata={"intent": intent.value})
            db.commit()
            return {"intent": intent.value, "response": response, "provider": settings.ai_provider}

    try:
        context = build_context_for_intent(db, ctx, intent.value, location_id, q)
    except AIContextError as exc:
        if exc.status_code == 403:
            response = {"answer": exc.message, "summary": exc.message, "denied": True}
            _record_interaction(db, ctx, session_id, intent.value, location_id, q, response, "DENIED", start)
            AuditService(db).record(action="AI_QUERY_DENIED", entity_type="ai_copilot", entity_id="query",
                                     actor_id=ctx.user_id, actor_email=ctx.email, metadata={"intent": intent.value})
            db.commit()
            return {"intent": intent.value, "response": response, "provider": settings.ai_provider}
        raise CopilotError(exc.code, exc.message, exc.status_code)

    provider = get_ai_provider(settings.ai_provider)
    try:
        structured = provider.generate_structured_response(intent.value, q, context, ctx.role.value)
    except Exception:
        response = {
            "answer": "AI assistance is temporarily unavailable. Visitor operations remain unaffected.",
            "summary": "Provider unavailable.",
            "unavailable": True,
            "limitations": ["AI-generated operational assistance. Verify important decisions in VMS."],
        }
        _record_interaction(db, ctx, session_id, intent.value, location_id, q, response, "FAILED", start)
        db.commit()
        return {"intent": intent.value, "response": response, "provider": settings.ai_provider}

    response = structured.to_dict()
    _record_interaction(db, ctx, session_id, intent.value, location_id, q, response, "COMPLETED", start)
    AuditService(db).record(
        action="AI_QUERY_EXECUTED", entity_type="ai_copilot", entity_id="query",
        actor_id=ctx.user_id, actor_email=ctx.email,
        metadata={"intent": intent.value, "location_id": location_id},
    )
    db.commit()
    return {
        "intent": intent.value,
        "response": response,
        "provider": settings.ai_provider,
        "context_scope": context.get("location_scope"),
    }


def _record_interaction(
    db: Session,
    ctx: AuthContext,
    session_id: Optional[int],
    intent: str,
    location_id: Optional[int],
    question: str,
    response: Dict[str, Any],
    status: str,
    start: float,
) -> None:
    duration_ms = int((time.monotonic() - start) * 1000)
    scope = {"location_id": location_id, "role": ctx.role.value}
    db.add(AIInteraction(
        user_id=ctx.user_id,
        session_id=session_id,
        intent=intent,
        location_scope_json=json.dumps(scope),
        question_redacted=redact_question(question),
        response_summary=(response.get("summary") or response.get("answer") or "")[:500],
        provider=settings.ai_provider,
        status=status,
        duration_ms=duration_ms,
    ))
