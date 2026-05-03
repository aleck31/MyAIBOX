"""Cognito USER_PASSWORD_AUTH end-to-end.

Credentials come from env (AIBOX_TEST_USERNAME / AIBOX_TEST_PASSWORD).
The test is skipped if they are not set — no hardcoded passwords.

After the SSO rename pass, CognitoAuth keys everything by `sub`, so we
verify that too.
"""
from __future__ import annotations

import pytest

from backend.common.auth import cognito_auth

pytestmark = pytest.mark.integration


def test_authenticate_returns_sub(cognito_test_credentials):
    username, password = cognito_test_credentials
    result = cognito_auth.authenticate(username, password)

    assert result["success"], f"authenticate failed: {result.get('error')}"
    assert result["sub"], "expected Cognito sub in result"
    assert result["tokens"]["AccessToken"]


def test_verify_token_round_trip(cognito_test_credentials):
    username, password = cognito_test_credentials
    auth = cognito_auth.authenticate(username, password)
    assert auth["success"]

    token = auth["tokens"]["AccessToken"]
    validated = cognito_auth.verify_token(token)
    assert validated == token


def test_logout_invalidates_token(cognito_test_credentials):
    username, password = cognito_test_credentials
    auth = cognito_auth.authenticate(username, password)
    token = auth["tokens"]["AccessToken"]

    assert cognito_auth.logout(token) is True
