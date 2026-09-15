"""Live Microsoft Graph email validation — approved test recipient only."""

import pytest

from app.application.email_provider import EmailMessage
from app.application.microsoft_graph_email_provider import MicrosoftGraphEmailProvider
from app.application.release_evidence import record_live_result
from app.core.config import settings
from app.domain.release_status import IntegrationReleaseStatus
from tests.integration.live.conftest import require_live_integration_enabled


@pytest.fixture(autouse=True)
def _live_guard():
    require_live_integration_enabled()
    if settings.email_provider != "ms_graph":
        pytest.skip("EMAIL_PROVIDER=ms_graph required")
    if not settings.email_live_test_recipient:
        pytest.skip("EMAIL_LIVE_TEST_RECIPIENT required")
    if not settings.validate_live_email_recipient(settings.email_live_test_recipient):
        pytest.fail("EMAIL_LIVE_TEST_RECIPIENT is not in LIVE_EMAIL_ALLOWED_RECIPIENTS allowlist")


def test_graph_live_validation_email():
    recipient = settings.email_live_test_recipient
    provider = MicrosoftGraphEmailProvider()
    result = provider.send(
        EmailMessage(
            to=recipient,
            subject="[VMS UAT] Microsoft Graph Email Validation",
            body="VMS Phase 16 live Graph connectivity test. No action required.",
            html_body="<p>VMS Phase 16 live Graph connectivity test. No action required.</p>",
        )
    )
    assert result.success, f"Graph send failed: {result.error_code} {result.error_message}"
    record_live_result(
        "graph_email",
        IntegrationReleaseStatus.LIVE_VALIDATED,
        f"delivered_to={recipient}",
    )
