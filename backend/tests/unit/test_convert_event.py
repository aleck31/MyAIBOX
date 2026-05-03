"""AgentProvider._convert_event turns Strands events into UI chunks.

Critical: tool_use -> toolResult pairing must survive interleaved text.
"""
from __future__ import annotations

from backend.genai.agents.provider import AgentProvider


def _convert(provider, event, state):
    return provider._convert_event(event, state)


def test_text_event_produces_text_chunk():
    p = AgentProvider.__new__(AgentProvider)  # skip __init__, only testing pure method
    out = _convert(p, {"data": "hello"}, {})
    assert out == {"text": "hello"}


def test_reasoning_event_produces_thinking_chunk():
    p = AgentProvider.__new__(AgentProvider)
    out = _convert(p, {"reasoning": True, "reasoningText": "let me think"}, {})
    assert out == {"thinking": "let me think"}


def test_unknown_event_returns_none():
    p = AgentProvider.__new__(AgentProvider)
    assert _convert(p, {"irrelevant": 1}, {}) is None


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


def test_tool_failure_maps_to_failed_status():
    p = AgentProvider.__new__(AgentProvider)
    state = {"tu-1": {"name": "search", "params": {"q": "x"}}}
    chunk = _convert(p, {
        "message": {
            "role": "user",
            "content": [{
                "toolResult": {
                    "toolUseId": "tu-1",
                    "status": "error",
                    "content": [{"text": "rate limited"}],
                }
            }],
        }
    }, state)
    assert chunk["tool_use"]["status"] == "failed"
    assert chunk["tool_use"]["result"] == "rate limited"


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
