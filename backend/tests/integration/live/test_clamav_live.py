"""Live ClamAV validation when ENABLE_LIVE_INTEGRATION_TESTS=true."""

import os
import tempfile

import pytest

from app.application.file_security_scanner import ScanResult, get_file_security_scanner
from app.application.release_evidence import record_live_result
from app.core.config import settings
from app.domain.release_status import IntegrationReleaseStatus
from tests.integration.live.conftest import require_live_integration_enabled

EICAR = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"


@pytest.fixture(autouse=True)
def _live_guard():
    require_live_integration_enabled()
    if settings.file_scanner_provider != "clamav":
        pytest.skip("FILE_SCANNER_PROVIDER=clamav required")
    if not settings.clamav_host:
        pytest.skip("CLAMAV_HOST not configured")


def test_clamav_clean_file_live():
    scanner = get_file_security_scanner()
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp:
        tmp.write(b"VMS UAT clean file scan test")
        path = tmp.name
    result = scanner.scan_file(path)
    os.unlink(path)
    assert result == ScanResult.CLEAN, f"Expected CLEAN, got {result}"
    record_live_result("clamav", IntegrationReleaseStatus.LIVE_VALIDATED, "clean_file=CLEAN")


def test_clamav_eicar_live():
    scanner = get_file_security_scanner()
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp:
        tmp.write(EICAR)
        path = tmp.name
    result = scanner.scan_file(path)
    os.unlink(path)
    assert result == ScanResult.INFECTED, f"Expected INFECTED for EICAR, got {result}"
    record_live_result("clamav", IntegrationReleaseStatus.LIVE_VALIDATED, "eicar=INFECTED")
