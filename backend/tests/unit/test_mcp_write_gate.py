"""MCP config writes: stdio servers run host commands, so they need an admin."""
from __future__ import annotations

import json

import os


# API modules build the Cognito singleton at import time; give it dummy config so
# these tests don't depend on a real .env. Must run before the imports below.
os.environ.setdefault("USER_POOL_ID", "unit-test-pool")
os.environ.setdefault("CLIENT_ID", "unit-test-client")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")

from backend.api import settings  # noqa: E402
from backend.core.config import app_config  # noqa: E402


# ── MCP write gate ──────────────────────────────────────────────────────────

def _set_admins(monkeypatch, value: str):
    monkeypatch.setenv("ADMIN_SUBS", value)


def test_mcp_stdio_denied_when_no_admin_configured(monkeypatch):
    _set_admins(monkeypatch, "")
    resp = settings._mcp_write_denied("anyone", "stdio")
    assert resp.status_code == 403
    assert json.loads(resp.body)["ok"] is False


def test_mcp_http_allowed_when_no_admin_configured(monkeypatch):
    _set_admins(monkeypatch, "")
    assert settings._mcp_write_denied("anyone", "http") is None
    assert settings._mcp_write_denied("anyone") is None


def test_mcp_writes_require_admin_when_configured(monkeypatch):
    _set_admins(monkeypatch, "admin-sub, other-admin")
    assert settings._mcp_write_denied("user", "http").status_code == 403
    assert settings._mcp_write_denied("user").status_code == 403
    assert settings._mcp_write_denied("admin-sub", "stdio") is None
    assert settings._mcp_write_denied("other-admin") is None


def test_admin_subs_parsing(monkeypatch):
    _set_admins(monkeypatch, " a , ,b,")
    assert app_config.admin_subs == frozenset({"a", "b"})
