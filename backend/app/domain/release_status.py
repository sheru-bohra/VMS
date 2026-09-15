"""Integration and release readiness classification."""

from enum import Enum


class IntegrationReleaseStatus(str, Enum):
    """Evidence-based integration maturity. Never assign higher states without proof."""

    NOT_CONFIGURED = "NOT_CONFIGURED"
    IMPLEMENTED = "IMPLEMENTED"
    MOCK_TESTED = "MOCK_TESTED"
    LIVE_VALIDATED = "LIVE_VALIDATED"
    UAT_APPROVED = "UAT_APPROVED"
    PRODUCTION_READY = "PRODUCTION_READY"


class ReleaseDecision(str, Enum):
    GO = "GO"
    CONDITIONAL_GO = "CONDITIONAL_GO"
    NO_GO = "NO_GO"
