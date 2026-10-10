"""Shared pytest fixtures.

Layout:
- tests/unit/ — no external deps. Use fakes / mocks. Fast. CI-safe.
- tests/integration/ — real AWS / LLM / Wikipedia / Cognito calls.
  Run only with `pytest -m integration` (opt-in).
"""
from __future__ import annotations

import os
from datetime import datetime
from typing import Optional

import pytest

# Keep test runs out of the service's log: logs/app.log is shared with production when the tests run on
# the same host, and tests fake errors on purpose (SECURITY_ALERT, "auth down", ...). This must run before
# any backend module is imported, because the logger reads it at import time. Override with LOG_TO_FILE=true.
os.environ.setdefault("LOG_TO_FILE", "false")

from backend.core.session.models import Session, SessionMetadata


@pytest.fixture
def make_session():
    """Factory for test Session objects. Does not touch DynamoDB."""
    def _make(
        session_id: str = "test-session",
        user_name: str = "test-sub",
        module_name: str = "assistant",
        model_id: Optional[str] = None,
    ) -> Session:
        return Session(
            session_id=session_id,
            session_name=f"{module_name} test",
            created_time=datetime.now(),
            updated_time=datetime.now(),
            user_name=user_name,
            metadata=SessionMetadata(module_name=module_name, model_id=model_id),
            history=[],
        )
    return _make


@pytest.fixture(scope="session")
def integration_enabled() -> bool:
    """True if integration tests should actually run (opt-in via marker)."""
    # Integration marker selection is handled by pytest -m. This fixture is
    # available for tests that need to check env-derived credentials.
    return True


@pytest.fixture(scope="session")
def cognito_test_credentials() -> tuple[str, str]:
    """Read Cognito test credentials from env. Skip test if missing.

    Required env vars:
        AIBOX_TEST_USERNAME, AIBOX_TEST_PASSWORD
    """
    username = os.getenv("AIBOX_TEST_USERNAME") or ""
    password = os.getenv("AIBOX_TEST_PASSWORD") or ""
    if not username or not password:
        pytest.skip("AIBOX_TEST_USERNAME / AIBOX_TEST_PASSWORD not set")
    return username, password


def pytest_ignore_collect(collection_path, config):
    """Don't even import integration tests unless they were asked for.

    Integration modules import real services at module level (e.g. the Cognito
    singleton), so deselecting by marker is too late — collection itself fails
    on machines without AWS/Cognito config. Opt in with `-m integration` or by
    passing an integration path explicitly.
    """
    if "integration" not in collection_path.parts:
        return None
    if "integration" in (config.getoption("markexpr") or "") and "not integration" not in config.getoption("markexpr"):
        return None
    if any("integration" in str(a) for a in config.invocation_params.args):
        return None
    return True
