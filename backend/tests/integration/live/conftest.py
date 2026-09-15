"""Live integration test guards."""

import os
import re

import pytest

UNSAFE_DB_PATTERNS = re.compile(r"(prod|production)(/|$|_)", re.I)
SAFE_DB_PATTERNS = re.compile(r"(test|staging|uat)", re.I)


def require_live_integration_enabled():
    if os.environ.get("ENABLE_LIVE_INTEGRATION_TESTS") != "true":
        pytest.skip("ENABLE_LIVE_INTEGRATION_TESTS=true required for live integration tests")


def validate_postgres_test_url(url: str) -> None:
    if os.environ.get("ALLOW_POSTGRES_TEST_DATABASE") != "true":
        pytest.skip("ALLOW_POSTGRES_TEST_DATABASE=true required")
    if UNSAFE_DB_PATTERNS.search(url) and not SAFE_DB_PATTERNS.search(url):
        pytest.fail(
            "TEST_POSTGRES_URL appears to target a non-test database. "
            "Refusing destructive integration tests."
        )
