"""Chat streaming: the AG-UI event order the client accepts, and a cached agent that is free after an abort.

Regression: the AG-UI client verifies the stream and aborts the run on a bad order. Chat emitted a tool
progress note as reasoning content with no reasoning message open whenever the model wrote some text and then
called a tool ("Cannot send 'REASONING_MESSAGE_CONTENT' event: No active reasoning message"). The aborted run
kept running on the server, so the agent stayed busy and the next message failed with "Agent is already
processing a request".
"""
from __future__ import annotations

import asyncio
import json
import os
import types

import pytest

os.environ.setdefault("USER_POOL_ID", "unit-test-pool")
os.environ.setdefault("CLIENT_ID", "unit-test-client")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")

from backend.api import chat  # noqa: E402
from backend.genai.agents.provider import AgentProvider  # noqa: E402

RUNNING = {"tool_use": {"name": "search", "status": "running", "tool_use_id": "t1"}}
DONE = {"tool_use": {"name": "search", "status": "completed", "tool_use_id": "t1", "params": {}, "result": "ok"}}

REPLIES = {
    "text then a tool call": [{"text": "Let me look. "}, RUNNING, DONE, {"text": "Done."}],
    "thinking, text, then a tool call": [{"thinking": "hmm"}, {"text": "Let me look. "}, RUNNING, DONE, {"text": "Done."}],
    "thinking again after the text": [{"thinking": "a"}, {"text": "b "}, {"thinking": "c"}],
}


class _ScriptedService:
    def __init__(self, chunks):
        self._chunks = chunks

    async def get_or_create_session(self, **_):
        return types.SimpleNamespace(session_id="s1", context={})

    async def streaming_reply_with_history(self, **_):
        for chunk in self._chunks:
            yield chunk


async def _events_for(chunks, monkeypatch):
    monkeypatch.setattr(chat, "_get_agent_service", lambda: _ScriptedService(chunks))
    monkeypatch.setattr(chat, "_build_tool_config", lambda _agent: {})
    monkeypatch.setattr(chat.skill_registry, "get_many", lambda _ids: [])
    agent = types.SimpleNamespace(id="a", workspace_enabled=False, prompt="p", enabled_skills=[], parameters={})
    response = await chat._stream_agent(
        agent=agent, sub="u", workspace_user="u", msg_text="hi", files=[], history=[],
        body=types.SimpleNamespace(thread_id="t"), run_id="r", message_id="m", thinking_id="th",
    )
    events = []
    async for raw in response.body_iterator:
        events += [json.loads(line[6:]) for line in raw.split("\n") if line.startswith("data: ")]
    return [e["type"] for e in events]


@pytest.mark.parametrize("name", REPLIES)
def test_reasoning_and_text_events_stay_in_a_valid_order(name, monkeypatch):
    """What the AG-UI client enforces: content only inside an open message, nothing open at RUN_FINISHED."""
    types_seen = asyncio.run(_events_for(REPLIES[name], monkeypatch))
    open_messages = set()
    for kind in types_seen:
        if kind.endswith("_MESSAGE_START"):
            open_messages.add(kind.split("_MESSAGE_")[0])
        elif kind.endswith("_MESSAGE_CONTENT"):
            assert kind.split("_MESSAGE_")[0] in open_messages, f"{kind} with no open message"
        elif kind.endswith("_MESSAGE_END"):
            open_messages.discard(kind.split("_MESSAGE_")[0])
        elif kind == "RUN_FINISHED":
            assert not open_messages, f"still open at RUN_FINISHED: {open_messages}"
    assert types_seen[-1] == "RUN_FINISHED"


def test_abandoning_a_turn_closes_the_strands_stream(monkeypatch):
    """The stream holds the agent's invocation lock; it must be released as soon as the consumer stops."""
    closed = []

    async def strands_stream(_prompt):
        try:
            for i in range(100):
                yield {"data": f"chunk{i}"}
        finally:
            closed.append(True)

    provider = AgentProvider.__new__(AgentProvider)
    provider._agent = types.SimpleNamespace(stream_async=lambda prompt, cancel_signal=None: strands_stream(prompt))
    provider._cycle_limit = types.SimpleNamespace(stop_message=None)
    provider.tool_config = {}
    provider._turn_cancel = None
    provider._idle = asyncio.Event()
    monkeypatch.setattr(provider, "_ensure_agent", lambda _history=None: provider._agent)

    async def consume_two_then_abandon():
        stream = provider.generate_stream("hi")
        await stream.__anext__()
        await stream.__anext__()
        await stream.aclose()
        # Checked here, before the event loop gets a chance to finalize the orphaned generator on its own.
        assert closed == [True]

    asyncio.run(consume_two_then_abandon())


def test_a_new_message_stops_a_turn_that_is_still_running(monkeypatch):
    """A turn whose client gave up kept the agent busy; the next message failed with "already processing"."""
    async def strands_stream(_prompt, cancel_signal):
        while not cancel_signal.is_set():          # a long turn (tool loop) that only ends when cancelled
            yield {"data": "."}
            await asyncio.sleep(0.01)

    provider = AgentProvider.__new__(AgentProvider)
    provider._agent = types.SimpleNamespace(stream_async=strands_stream)
    provider._cycle_limit = types.SimpleNamespace(stop_message=None)
    provider.tool_config = {}
    provider._turn_cancel = None
    provider._idle = asyncio.Event()
    provider._idle.set()
    monkeypatch.setattr(provider, "_ensure_agent", lambda _history=None: provider._agent)

    async def scenario():
        async def old_turn():
            async for _ in provider.generate_stream("long question"):
                pass
        running = asyncio.create_task(old_turn())
        await asyncio.sleep(0.05)
        assert await provider.supersede_running_turn(timeout=1.0)
        await asyncio.wait_for(running, 1.0)       # the old turn ended instead of holding the agent

    asyncio.run(scenario())

