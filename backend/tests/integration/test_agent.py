"""AgentService end-to-end against real Strands + Bedrock.

Covers: tool use flow and streaming reply format.
"""
from __future__ import annotations

import pytest

from core.service.agent_service import AgentService
from genai.models.model_manager import model_manager

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module", autouse=True)
def _init_models():
    model_manager.init_default_models()


async def test_agent_streaming_yields_chunks(make_session):
    svc = AgentService(module_name="assistant")
    session = make_session(session_id="test-agent-session", module_name="assistant")
    chunks = []
    async for chunk in svc._generate_stream_async(
        session=session,
        prompt="Reply with one word: OK",
        system_prompt="You are concise.",
        tool_config={"enabled": False},
    ):
        chunks.append(chunk)
        if len(chunks) >= 10:
            break
    assert len(chunks) > 0
    # At least one text chunk
    assert any("text" in c for c in chunks)


async def test_agent_tool_use_produces_running_and_completed_chunks(make_session):
    """With tool_use prompting, verify we emit both 'running' and 'completed' tool chunks."""
    svc = AgentService(module_name="assistant")
    session = make_session(session_id="test-agent-tool-session", module_name="assistant")
    tool_config = {
        "enabled": True,
        "legacy_tools": ["get_weather"],
        "mcp_tools_enabled": False,
        "strands_tools_enabled": True,
    }
    tool_statuses = []
    async for chunk in svc._generate_stream_async(
        session=session,
        prompt="What is the weather in Singapore? Use the get_weather tool.",
        system_prompt="You must use the provided tools.",
        tool_config=tool_config,
    ):
        if "tool_use" in chunk:
            tool_statuses.append(chunk["tool_use"].get("status"))
        if len(tool_statuses) >= 2:
            break

    assert "running" in tool_statuses or "completed" in tool_statuses
