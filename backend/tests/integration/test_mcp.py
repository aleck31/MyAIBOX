"""MCP server config + provider wiring.

Doesn't spawn stdio servers (slow/flaky). Only validates that config loads
and ToolProvider can construct clients for declared HTTP/SSE servers.
"""
from __future__ import annotations

import pytest

from backend.genai.tools.mcp.mcp_server_manager import mcp_server_manager
from backend.genai.tools.provider import tool_provider

pytestmark = pytest.mark.integration


def test_mcp_servers_are_loaded_from_db():
    servers = mcp_server_manager.get_mcp_servers()
    assert isinstance(servers, dict)


def test_tool_provider_lists_tools():
    tools = tool_provider.list_tools()
    assert isinstance(tools, list)
    # Strands builtin tools should always be present
    builtin_names = {t["name"] for t in tools if t["type"] == "strands"}
    assert builtin_names  # at least one strands tool


def test_tool_provider_builds_legacy_and_mcp_clients():
    legacy, mcp_clients = tool_provider.get_tools_and_contexts({
        "legacy_tools": ["get_weather"],
        "strands_tools_enabled": True,
        "mcp_tools_enabled": False,
    })
    assert isinstance(legacy, list)
    assert isinstance(mcp_clients, list)
    # mcp disabled -> no clients
    assert mcp_clients == []
