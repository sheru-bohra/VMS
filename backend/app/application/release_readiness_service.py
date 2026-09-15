"""Release candidate readiness matrix and GO / NO_GO decision."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.application.release_evidence import load_evidence
from app.core.config import settings
from app.domain.release_status import IntegrationReleaseStatus, ReleaseDecision


def _classify_core_vms(automated_tests_passed: bool = True) -> IntegrationReleaseStatus:
    if automated_tests_passed:
        return IntegrationReleaseStatus.UAT_APPROVED
    return IntegrationReleaseStatus.MOCK_TESTED


def _classify_from_evidence(
    component: str,
    configured: bool,
    mock_capable: bool,
    production_required: bool,
) -> IntegrationReleaseStatus:
    evidence = load_evidence().get(component, {})
    recorded = evidence.get("status")
    if recorded:
        try:
            return IntegrationReleaseStatus(recorded)
        except ValueError:
            pass
    if not configured:
        if production_required:
            return IntegrationReleaseStatus.NOT_CONFIGURED
        return IntegrationReleaseStatus.NOT_CONFIGURED
    if mock_capable and settings.app_env != "production":
        return IntegrationReleaseStatus.MOCK_TESTED
    return IntegrationReleaseStatus.IMPLEMENTED


def _postgres_required() -> bool:
    return settings.is_production


def _entra_required() -> bool:
    return settings.is_production


def _graph_required() -> bool:
    return False


def _clamav_required() -> bool:
    return settings.is_production and settings.file_scanner_provider == "clamav"


def build_release_matrix(automated_tests_passed: bool = True) -> Dict[str, str]:
    evidence = load_evidence()
    matrix: Dict[str, str] = {
        "core_vms": _classify_core_vms(automated_tests_passed).value,
        "postgresql": evidence.get("postgresql", {}).get("status")
        or _classify_from_evidence(
            "postgresql",
            settings.resolved_database_url().startswith("postgresql"),
            mock_capable=True,
            production_required=_postgres_required(),
        ).value,
        "entra": evidence.get("entra", {}).get("status")
        or _classify_from_evidence(
            "entra",
            bool(settings.entra_tenant_id and settings.entra_client_id),
            mock_capable=True,
            production_required=_entra_required(),
        ).value,
        "graph_email": IntegrationReleaseStatus.NOT_CONFIGURED.value,
        "clamav": evidence.get("clamav", {}).get("status")
        or _classify_from_evidence(
            "clamav",
            settings.file_scanner_provider == "clamav",
            mock_capable=True,
            production_required=_clamav_required(),
        ).value,
        "access_control": evidence.get("access_control", {}).get("status")
        or (
            IntegrationReleaseStatus.NOT_CONFIGURED.value
            if not settings.access_control_enabled
            else IntegrationReleaseStatus.MOCK_TESTED.value
        ),
        "badge_printer": evidence.get("badge_printer", {}).get("status")
        or (
            IntegrationReleaseStatus.NOT_CONFIGURED.value
            if not settings.badge_printer_enabled
            else IntegrationReleaseStatus.MOCK_TESTED.value
        ),
        "ai_provider": (
            IntegrationReleaseStatus.NOT_CONFIGURED.value
            if not settings.ai_enabled
            else IntegrationReleaseStatus.MOCK_TESTED.value
        ),
        "audit_integrity": evidence.get("audit_integrity", {}).get("status")
        or IntegrationReleaseStatus.IMPLEMENTED.value,
    }
    return matrix


def evaluate_release_decision(
    matrix: Optional[Dict[str, str]] = None,
    automated_tests_passed: bool = True,
    audit_valid: bool = True,
    build_passed: bool = True,
    security_passed: bool = True,
) -> Dict[str, Any]:
    matrix = matrix or build_release_matrix(automated_tests_passed)
    blockers: List[str] = []
    highs: List[str] = []
    conditions: List[str] = []

    if not automated_tests_passed:
        blockers.append("Automated test suite did not pass.")
    if not audit_valid:
        blockers.append("Audit integrity is not VALID.")
    if not build_passed:
        blockers.append("Frontend production build failed.")
    if not security_passed:
        blockers.append("Security check failed.")

    live_required = {
        "postgresql": _postgres_required(),
        "entra": _entra_required(),
        "graph_email": _graph_required(),
        "clamav": _clamav_required(),
    }
    for component, required in live_required.items():
        status = matrix.get(component, IntegrationReleaseStatus.NOT_CONFIGURED.value)
        if required and status not in (
            IntegrationReleaseStatus.LIVE_VALIDATED.value,
            IntegrationReleaseStatus.UAT_APPROVED.value,
            IntegrationReleaseStatus.PRODUCTION_READY.value,
        ):
            blockers.append(f"GO-LIVE BLOCKED: LIVE {component.upper().replace('_', ' ')} VALIDATION REQUIRED")

    if settings.access_control_enabled and matrix.get("access_control") == IntegrationReleaseStatus.MOCK_TESTED.value:
        conditions.append("Access control enabled but only MOCK_TESTED — disable or live-validate before production.")
    if settings.badge_printer_enabled and matrix.get("badge_printer") == IntegrationReleaseStatus.MOCK_TESTED.value:
        conditions.append("Badge printer enabled but only MOCK_TESTED — disable or live-validate before production.")

    if blockers:
        decision = ReleaseDecision.NO_GO
    elif conditions:
        decision = ReleaseDecision.CONDITIONAL_GO
    else:
        decision = ReleaseDecision.GO

    return {
        "decision": decision.value,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "release_version": settings.app_release_version,
        "matrix": matrix,
        "blockers": blockers,
        "high": highs,
        "conditions": conditions,
        "live_validation_required": [
            k for k, v in live_required.items() if v and matrix.get(k) not in (
                IntegrationReleaseStatus.LIVE_VALIDATED.value,
                IntegrationReleaseStatus.UAT_APPROVED.value,
                IntegrationReleaseStatus.PRODUCTION_READY.value,
            )
        ],
    }
