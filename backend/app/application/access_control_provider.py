"""Vendor-neutral physical access control provider abstraction."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional

from app.core.config import settings


class ProviderHealth:
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"
    DISABLED = "DISABLED"


@dataclass
class AccessCredentialRequest:
    credential_id: int
    visit_id: int
    location_id: int
    access_profile_external_ref: str
    visitor_display_name: str
    visitor_type_name: Optional[str]
    valid_from: datetime
    valid_until: datetime
    idempotency_key: str


@dataclass
class ProvisionResult:
    success: bool
    provider_credential_reference: Optional[str] = None
    error_code: Optional[str] = None
    transient: bool = False


@dataclass
class RevokeResult:
    success: bool
    error_code: Optional[str] = None
    transient: bool = False


@dataclass
class AccessStatusResult:
    status: str
    error_code: Optional[str] = None


class AccessControlProvider(ABC):
    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        ...

    @abstractmethod
    def capabilities(self) -> Dict[str, bool]:
        ...

    @abstractmethod
    def provision_access(self, request: AccessCredentialRequest) -> ProvisionResult:
        ...

    @abstractmethod
    def revoke_access(self, provider_credential_reference: str) -> RevokeResult:
        ...

    @abstractmethod
    def get_access_status(self, provider_credential_reference: str) -> AccessStatusResult:
        ...


class DisabledAccessControlProvider(AccessControlProvider):
    def health_check(self) -> Dict[str, Any]:
        return {"status": ProviderHealth.DISABLED, "reason_code": "DISABLED"}

    def capabilities(self) -> Dict[str, bool]:
        return {
            "supports_timed_access": False,
            "supports_immediate_revoke": False,
            "supports_status_query": False,
        }

    def provision_access(self, request: AccessCredentialRequest) -> ProvisionResult:
        return ProvisionResult(success=False, error_code="PROVIDER_DISABLED", transient=False)

    def revoke_access(self, provider_credential_reference: str) -> RevokeResult:
        return RevokeResult(success=True)

    def get_access_status(self, provider_credential_reference: str) -> AccessStatusResult:
        return AccessStatusResult(status="DISABLED")


class DevMockAccessControlProvider(AccessControlProvider):
    last_provision_request: Optional[AccessCredentialRequest] = None

    def health_check(self) -> Dict[str, Any]:
        if settings.access_mock_simulate_unavailable:
            return {"status": ProviderHealth.UNAVAILABLE, "reason_code": "MOCK_UNAVAILABLE"}
        return {"status": ProviderHealth.HEALTHY, "reason_code": "MOCK_OK"}

    def capabilities(self) -> Dict[str, bool]:
        return {
            "supports_timed_access": True,
            "supports_immediate_revoke": True,
            "supports_status_query": True,
        }

    def provision_access(self, request: AccessCredentialRequest) -> ProvisionResult:
        DevMockAccessControlProvider.last_provision_request = request
        if settings.access_mock_simulate_unavailable:
            return ProvisionResult(success=False, error_code="PROVIDER_UNAVAILABLE", transient=True)
        if settings.access_mock_simulate_failure:
            return ProvisionResult(success=False, error_code="MOCK_PROVISION_FAILED", transient=False)
        ref = f"dev-mock-cred-{request.credential_id}"
        return ProvisionResult(success=True, provider_credential_reference=ref)

    def revoke_access(self, provider_credential_reference: str) -> RevokeResult:
        if settings.access_mock_simulate_unavailable:
            return RevokeResult(success=False, error_code="PROVIDER_UNAVAILABLE", transient=True)
        return RevokeResult(success=True)

    def get_access_status(self, provider_credential_reference: str) -> AccessStatusResult:
        if settings.access_mock_simulate_unavailable:
            return AccessStatusResult(status="UNAVAILABLE", error_code="MOCK_UNAVAILABLE")
        return AccessStatusResult(status="ACTIVE")


def get_access_control_provider(provider_key: Optional[str] = None) -> AccessControlProvider:
    key = provider_key or settings.access_control_provider
    if key == "dev_mock":
        return DevMockAccessControlProvider()
    if key == "disabled":
        return DisabledAccessControlProvider()
    return DisabledAccessControlProvider()
