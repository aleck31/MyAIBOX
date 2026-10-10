"""Secrets Manager parsing."""
from __future__ import annotations

import pytest


# ── secrets ─────────────────────────────────────────────────────────────────

class _FakeSecrets:
    def __init__(self, secret: str):
        self._secret = secret

    def get_secret_value(self, SecretId):
        return {"SecretString": self._secret}


@pytest.mark.parametrize("raw", ['{"api_key": "k", "on": true}', "{'api_key': 'k', 'on': True}"])
def test_get_secret_parses_json_and_legacy_python_repr(monkeypatch, raw):
    from backend.utils import aws
    monkeypatch.setattr(aws, "get_aws_client", lambda *_a, **_k: _FakeSecrets(raw))
    assert aws.get_secret("x") == {"api_key": "k", "on": True}
