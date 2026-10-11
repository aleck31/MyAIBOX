"""AgentProvider._convert_event turns Strands events into UI chunks.

Critical: tool_use -> toolResult pairing must survive interleaved text.
"""
from __future__ import annotations

from backend.genai.agents.provider import AgentProvider


def _convert(provider, event, state):
    return provider._convert_event(event, state)


def test_tool_use_roundtrip_tracks_state():
    p = AgentProvider.__new__(AgentProvider)
    state = {}

    # Tool call announced
    chunk = _convert(p, {
        "current_tool_use": {
            "toolUseId": "tu-1",
            "name": "get_weather",
            "input": {"place": "Singapore"},
        }
    }, state)
    assert chunk == {"tool_use": {
        "name": "get_weather",
        "params": {"place": "Singapore"},
        "status": "running",
        "tool_use_id": "tu-1",
    }}
    assert state["tool_1" if False else "tu-1"]["name"] == "get_weather"

    # Tool result comes back
    chunk = _convert(p, {
        "message": {
            "role": "user",
            "content": [{
                "toolResult": {
                    "toolUseId": "tu-1",
                    "status": "success",
                    "content": [{"text": "32C sunny"}],
                }
            }],
        }
    }, state)
    assert chunk == {"tool_use": {
        "name": "get_weather",
        "params": {"place": "Singapore"},
        "status": "completed",
        "result": "32C sunny",
        "tool_use_id": "tu-1",
    }}
    # State cleared after pairing
    assert "tu-1" not in state


def test_tool_input_as_json_string_is_parsed():
    p = AgentProvider.__new__(AgentProvider)
    state = {}
    chunk = _convert(p, {
        "current_tool_use": {
            "toolUseId": "tu-2",
            "name": "calc",
            "input": '{"expr": "1+1"}',
        }
    }, state)
    assert chunk["tool_use"]["params"] == {"expr": "1+1"}
