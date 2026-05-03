"""Legacy tools — external HTTP calls to Wikipedia, DDGS, weather API.

These external services can be flaky; mark as integration and run only on
demand.
"""
from __future__ import annotations

import pytest

from backend.genai.tools.legacy.tool_registry import legacy_tool_registry

pytestmark = pytest.mark.integration


async def test_search_wikipedia_returns_result():
    result = await legacy_tool_registry.execute_tool(
        "search_wikipedia", query="Amazon Web Services"
    )
    assert result


async def test_search_internet_returns_result():
    result = await legacy_tool_registry.execute_tool(
        "search_internet", query="python language"
    )
    assert result


async def test_get_weather_returns_result():
    result = await legacy_tool_registry.execute_tool(
        "get_weather", place="Singapore"
    )
    assert result
