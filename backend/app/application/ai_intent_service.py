"""Deterministic intent classification for VMS Copilot."""

from __future__ import annotations

from enum import Enum
from typing import Optional, Tuple


class CopilotIntent(str, Enum):
    OPERATIONAL_SUMMARY = "OPERATIONAL_SUMMARY"
    ONSITE_QUERY = "ONSITE_QUERY"
    EXPECTED_QUERY = "EXPECTED_QUERY"
    APPROVAL_QUERY = "APPROVAL_QUERY"
    SECURITY_REVIEW_QUERY = "SECURITY_REVIEW_QUERY"
    COMPLIANCE_QUERY = "COMPLIANCE_QUERY"
    VISITOR_HISTORY_QUERY = "VISITOR_HISTORY_QUERY"
    OVERSTAY_QUERY = "OVERSTAY_QUERY"
    EMERGENCY_QUERY = "EMERGENCY_QUERY"
    MANAGEMENT_SUMMARY = "MANAGEMENT_SUMMARY"
    LOCATION_COMPARISON = "LOCATION_COMPARISON"
    TREND_QUERY = "TREND_QUERY"
    UNSUPPORTED = "UNSUPPORTED"
    UNKNOWN = "UNKNOWN"


MANAGEMENT_INTENTS = frozenset({
    CopilotIntent.MANAGEMENT_SUMMARY,
    CopilotIntent.LOCATION_COMPARISON,
    CopilotIntent.TREND_QUERY,
})


def classify_intent(question: str) -> Tuple[CopilotIntent, Optional[str]]:
    q = question.lower().strip()
    if not q:
        return CopilotIntent.UNKNOWN, None

    unsupported_markers = [
        "employee attendance",
        "payroll",
        "salary",
        "hr record",
        "password",
        "api key",
    ]
    for m in unsupported_markers:
        if m in q:
            return CopilotIntent.UNSUPPORTED, "VMS Copilot only has access to visitor-management information."

    if any(x in q for x in ["compare", "comparison", "across location", "all location", "all offices", "cross location"]):
        if any(x in q for x in ["month", "week", "trend", "volume", "activity"]):
            return CopilotIntent.LOCATION_COMPARISON, None
        return CopilotIntent.LOCATION_COMPARISON, None

    if any(x in q for x in ["trend", "this week", "last week", "this month", "last month", "changed", "volume"]):
        if "management" in q or "compare" in q or "all location" in q:
            return CopilotIntent.TREND_QUERY, None

    if any(x in q for x in ["management briefing", "daily briefing", "today's briefing", "executive"]):
        return CopilotIntent.MANAGEMENT_SUMMARY, None

    if any(x in q for x in ["attention", "needs action", "what needs", "summary", "briefing", "operational summary"]):
        return CopilotIntent.OPERATIONAL_SUMMARY, None

    if "onsite" in q or "on site" in q or "on-site" in q:
        return CopilotIntent.ONSITE_QUERY, None

    if "expected" in q or "arriving" in q:
        return CopilotIntent.EXPECTED_QUERY, None

    if "approval" in q or "pending" in q and "approve" in q:
        return CopilotIntent.APPROVAL_QUERY, None

    if "security review" in q or "security attention" in q:
        return CopilotIntent.SECURITY_REVIEW_QUERY, None

    if "compliance" in q or "contractor" in q and "document" in q:
        return CopilotIntent.COMPLIANCE_QUERY, None

    if "overstay" in q or "overstayed" in q or "beyond expected" in q:
        return CopilotIntent.OVERSTAY_QUERY, None

    if "emergency" in q or "roll-call" in q or "roll call" in q or "evacuation" in q:
        return CopilotIntent.EMERGENCY_QUERY, None

    if "history" in q or "visited before" in q or "previous visit" in q:
        return CopilotIntent.VISITOR_HISTORY_QUERY, None

    if "who is" in q or "how many" in q:
        return CopilotIntent.OPERATIONAL_SUMMARY, None

    return CopilotIntent.UNKNOWN, None
