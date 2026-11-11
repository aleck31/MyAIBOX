"""MCP config writes: stdio servers run host commands, so they need an admin."""
from __future__ import annotations

import json

import os


os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")

from backend.api import settings  # noqa: E402


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
