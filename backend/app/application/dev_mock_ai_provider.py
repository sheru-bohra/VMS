"""Development mock AI provider — deterministic structured responses."""

from __future__ import annotations

from typing import Any, Dict, List

from app.application.ai_provider import (
    AIInsightItem,
    AIRecommendedAction,
    AISourceReference,
    AIStructuredResponse,
    AIProvider,
)


class DevMockAIProvider(AIProvider):
    def generate_structured_response(
        self,
        intent: str,
        question: str,
        context: Dict[str, Any],
        role: str,
    ) -> AIStructuredResponse:
        if context.get("denied"):
            return AIStructuredResponse(
                answer=context.get("denial_message", "Access denied."),
                summary="Request outside authorized scope.",
                denied=True,
                limitations=["AI-generated operational assistance. Verify important decisions in VMS."],
            )

        ops = context.get("operational_summary", {})
        locations = ops.get("locations", {})
        onsite_total = sum(v.get("onsite_now", 0) for v in locations.values())
        pending_total = sum(v.get("pending_approval", 0) for v in locations.values())
        emergencies = context.get("active_emergencies", ops.get("active_emergencies", 0))
        overstay_count = len(context.get("overstays", []))
        security = context.get("security_summary", {})
        compliance_count = len(context.get("compliance_attention", []))

        insights: List[AIInsightItem] = []
        actions: List[AIRecommendedAction] = []
        sources: List[AISourceReference] = []
        limitations = ["AI-generated operational assistance. Verify important decisions in VMS."]

        if emergencies and isinstance(emergencies, list) and len(emergencies) > 0:
            e = emergencies[0]
            insights.append(AIInsightItem(
                type="EMERGENCY",
                title="Active emergency roll-call",
                explanation=f"{e.get('location_name')} has an active visitor emergency.",
                priority="URGENT",
                evidence=[f"Visitors at start: {e.get('visitor_snapshot_count', 0)}"],
            ))
            actions.append(AIRecommendedAction("Open Emergency Roll-Call", "/emergency-roll-call"))
            sources.append(AISourceReference(label=f"{e.get('location_name')} Emergency", path="/emergency-roll-call"))

        if intent in ("MANAGEMENT_SUMMARY", "LOCATION_COMPARISON", "TREND_QUERY"):
            mgmt = context.get("management_dashboard", {})
            kpis = mgmt.get("kpis", {})
            loc_rows = mgmt.get("locations", [])
            answer_parts = [
                f"Expected today: {kpis.get('expected_today', 0)}",
                f"Checked in today: {kpis.get('checked_in_today', 0)}",
                f"Currently onsite: {kpis.get('onsite_now', 0)}",
                f"Pending approval: {kpis.get('awaiting_approval', 0)}",
            ]
            if loc_rows:
                sources.append(AISourceReference(label="Management Dashboard", path="/dashboard"))
            answer = "Today's briefing — " + "; ".join(answer_parts) + "."
            summary = answer
            if loc_rows:
                top = loc_rows[0]
                insights.append(AIInsightItem(
                    type="MANAGEMENT",
                    title="Location activity",
                    explanation=f"{top.get('location_name')}: {top.get('visitors', 0)} visitors, {top.get('check_ins', 0)} check-ins.",
                    priority="INFORMATION",
                ))
            return AIStructuredResponse(
                answer=answer,
                summary=summary,
                insights=insights,
                recommended_actions=actions + [AIRecommendedAction("Open Dashboard", "/dashboard")],
                source_references=sources,
                limitations=limitations,
            )

        attention_items = []
        if pending_total:
            attention_items.append(f"{pending_total} visitor(s) awaiting approval")
        if overstay_count:
            attention_items.append(f"{overstay_count} overstayed visitor(s)")
        if security.get("review_count", 0):
            attention_items.append(f"{security.get('review_count')} security review(s)")
        if compliance_count:
            attention_items.append(f"{compliance_count} compliance item(s)")

        scope_label = ", ".join(context.get("location_scope", [])) or "authorized locations"
        if not attention_items and not emergencies:
            answer = f"No urgent items in {scope_label}. Onsite: {onsite_total}."
        else:
            answer = f"{len(attention_items) + (1 if emergencies else 0)} item(s) need attention in {scope_label}: " + "; ".join(attention_items) + "."

        if pending_total:
            actions.append(AIRecommendedAction("Review Pending Approvals", "/approvals"))
            sources.append(AISourceReference(label="Pending Approvals", path="/approvals"))
        if overstay_count:
            actions.append(AIRecommendedAction("View Onsite Visitors", "/onsite-now"))
        if security.get("review_count", 0):
            actions.append(AIRecommendedAction("Open Security Review", "/security-review"))
        if compliance_count:
            actions.append(AIRecommendedAction("Review Contractor Compliance", "/vendors-contractors"))
        if onsite_total:
            sources.append(AISourceReference(label=f"{scope_label} Onsite", path="/onsite-now"))

        if overstay_count:
            for o in context.get("overstays", [])[:3]:
                insights.append(AIInsightItem(
                    type="OVERSTAY",
                    title="Overstay requires attention",
                    explanation=f"{o.get('visitor_name')} — {o.get('overdue_minutes', 0)} minutes beyond expected duration.",
                    priority="ATTENTION",
                    evidence=[f"Visit {o.get('registration_reference')}"],
                ))

        return AIStructuredResponse(
            answer=answer,
            summary=answer,
            insights=insights,
            recommended_actions=actions,
            source_references=sources,
            limitations=limitations,
        )


def get_ai_provider(provider_name: str) -> AIProvider:
    if provider_name == "dev_mock":
        return DevMockAIProvider()
    if provider_name == "disabled":
        return DevMockAIProvider()
    return DevMockAIProvider()
