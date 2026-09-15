"""Vendor-neutral badge printer provider abstraction."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional

from app.core.config import settings


class PrinterHealth:
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    OFFLINE = "OFFLINE"
    DISABLED = "DISABLED"
    UNKNOWN = "UNKNOWN"


@dataclass
class BadgePrintPayload:
    badge_number: str
    visitor_name: str
    company: Optional[str]
    visitor_type: Optional[str]
    host_name: Optional[str]
    location_name: str
    validity_text: Optional[str]
    template_version: str = "badge-template-v1"


@dataclass
class PrintResult:
    success: bool
    provider_job_reference: Optional[str] = None
    error_code: Optional[str] = None
    transient: bool = False


@dataclass
class PrintJobStatusResult:
    status: str
    error_code: Optional[str] = None


class BadgePrinterProvider(ABC):
    @abstractmethod
    def health_check(self, printer_external_ref: Optional[str] = None) -> Dict[str, Any]:
        ...

    @abstractmethod
    def print_badge(
        self,
        printer_reference: str,
        badge_payload: BadgePrintPayload,
        idempotency_key: str,
    ) -> PrintResult:
        ...

    @abstractmethod
    def get_job_status(self, provider_job_reference: str) -> PrintJobStatusResult:
        ...


class DisabledBadgePrinterProvider(BadgePrinterProvider):
    def health_check(self, printer_external_ref: Optional[str] = None) -> Dict[str, Any]:
        return {"status": PrinterHealth.DISABLED, "reason_code": "DISABLED"}

    def print_badge(
        self,
        printer_reference: str,
        badge_payload: BadgePrintPayload,
        idempotency_key: str,
    ) -> PrintResult:
        return PrintResult(success=False, error_code="PRINTER_DISABLED", transient=False)

    def get_job_status(self, provider_job_reference: str) -> PrintJobStatusResult:
        return PrintJobStatusResult(status="DISABLED")


class DevMockBadgePrinterProvider(BadgePrinterProvider):
    last_print_payload: Optional[BadgePrintPayload] = None
    last_idempotency_key: Optional[str] = None

    def health_check(self, printer_external_ref: Optional[str] = None) -> Dict[str, Any]:
        if settings.badge_printer_mock_simulate_offline:
            return {"status": PrinterHealth.OFFLINE, "reason_code": "MOCK_OFFLINE"}
        return {"status": PrinterHealth.HEALTHY, "reason_code": "MOCK_OK"}

    def print_badge(
        self,
        printer_reference: str,
        badge_payload: BadgePrintPayload,
        idempotency_key: str,
    ) -> PrintResult:
        DevMockBadgePrinterProvider.last_print_payload = badge_payload
        DevMockBadgePrinterProvider.last_idempotency_key = idempotency_key
        if settings.badge_printer_mock_simulate_offline:
            return PrintResult(success=False, error_code="PRINTER_OFFLINE", transient=True)
        ref = f"dev-mock-print-{idempotency_key}"
        return PrintResult(success=True, provider_job_reference=ref)

    def get_job_status(self, provider_job_reference: str) -> PrintJobStatusResult:
        return PrintJobStatusResult(status="PRINTED")


def get_badge_printer_provider(provider_key: Optional[str] = None) -> BadgePrinterProvider:
    key = provider_key or settings.badge_printer_provider
    if key == "dev_mock":
        return DevMockBadgePrinterProvider()
    return DisabledBadgePrinterProvider()
