"""End-to-end AgentService session cache behavior.

Covers the contract the UI depends on:
- Turn 2 in the same session reuses the cached AgentProvider (no re-init).
- update_session_model hot-swaps the underlying model without rebuilding.
- After eviction, next turn restores history from DynamoDB into the new Agent.

All external dependencies (Strands Agent, Bedrock, DynamoDB) are faked so this
runs in tests/unit/ alongside the fast suite.
"""
from __future__ import annotations

from typing import List, Optional

import pytest

from backend.core.service import agent_service as agent_service_module
from backend.core.service.agent_service import AgentService


class FakeProvider:
    """Stand-in for genai.agents.provider.AgentProvider."""

    instances: list["FakeProvider"] = []

    def __init__(self, model_id: str, system_prompt: str = "", tool_config: Optional[dict] = None):
        self.model_id = model_id
        self.system_prompt = system_prompt
        self.tool_config = tool_config or {}
        self.messages: List[dict] = []
        self.destroyed = False
        self.init_history: Optional[List] = None
        self.stream_calls: list[str] = []
        FakeProvider.instances.append(self)

    def _ensure_agent(self, history_messages=None):
        self.init_history = list(history_messages) if history_messages else []
        # Mirror the init history into self.messages like the real provider does
        if history_messages:
            for msg in history_messages:
                role = msg.get("role") if isinstance(msg, dict) else getattr(msg, "role", "")
                content = msg.get("content") if isinstance(msg, dict) else getattr(msg, "content", "")
                self.messages.append({"role": role, "content": content})

    def update_model(self, model_id: str):
        self.model_id = model_id

    async def generate_stream(self, prompt):
        self.stream_calls.append(prompt if isinstance(prompt, str) else str(prompt))
        # Record the user turn + fake an assistant reply
        self.messages.append({"role": "user", "content": [{"text": str(prompt)}]})
        yield {"text": "ok-reply"}
        self.messages.append({"role": "assistant", "content": [{"text": "ok-reply"}]})

    def destroy(self):
        self.destroyed = True


@pytest.fixture(autouse=True)
def patch_provider(monkeypatch):
    FakeProvider.instances.clear()
    monkeypatch.setattr(agent_service_module, "AgentProvider", FakeProvider)
    yield
    FakeProvider.instances.clear()


@pytest.fixture
def svc(monkeypatch, make_session):
    """AgentService with session-related IO stubbed out."""
    s = AgentService(module_name="assistant")

    # No need to hit DynamoDB for session history / model lookup / persistence
    async def fake_load_history(session):
        return getattr(session, "_fake_db_history", [])

    async def fake_get_model(session):
        return session.metadata.model_id or "default-model"

    async def fake_save(session):
        session._fake_db_history = session.history

    monkeypatch.setattr(s, "load_session_history", fake_load_history)
    monkeypatch.setattr(s, "get_session_model", fake_get_model)
    monkeypatch.setattr(s.session_store, "save_session", fake_save)
    return s


async def _drain(gen):
    return [chunk async for chunk in gen]


async def test_turn_two_reuses_cached_provider(svc, make_session):
    session = make_session(session_id="sid-1", model_id="m1")

    await _drain(svc.streaming_reply_with_history(
        session=session, message="hi", system_prompt="",
        history=[], tool_config={}, persist=False,
    ))
    await _drain(svc.streaming_reply_with_history(
        session=session, message="hi again", system_prompt="",
        history=[], tool_config={}, persist=False,
    ))

    # Exactly one provider was constructed; both turns hit the same one
    assert len(FakeProvider.instances) == 1
    provider = FakeProvider.instances[0]
    assert len(provider.stream_calls) == 2


async def test_model_hot_swap_updates_same_provider(svc, make_session):
    session = make_session(session_id="sid-swap", model_id="m1")

    await _drain(svc.streaming_reply_with_history(
        session=session, message="first", system_prompt="",
        history=[], tool_config={}, persist=False,
    ))
    initial_provider = FakeProvider.instances[0]
    assert initial_provider.model_id == "m1"

    # Simulate UI-triggered model change
    session.metadata.model_id = "m2"
    svc.model_id = None  # BaseService caches model_id on the service; reset it

    await _drain(svc.streaming_reply_with_history(
        session=session, message="second", system_prompt="",
        history=[], tool_config={}, persist=False,
    ))

    # Same provider instance — hot-swapped, not rebuilt
    assert len(FakeProvider.instances) == 1
    assert initial_provider.model_id == "m2"


async def test_eviction_rebuilds_provider_with_db_history(svc, make_session):
    session = make_session(session_id="sid-evict", model_id="m1")

    # Turn 1 with persistence on -> history lands in the fake "DB"
    await _drain(svc.streaming_reply_with_history(
        session=session, message="hello", system_prompt="",
        history=[], tool_config={}, persist=True,
    ))
    # Sanity: our fake save wrote history back onto the session
    assert len(session._fake_db_history) >= 1

    # Simulate TTL eviction — old provider destroyed, cache cleared
    svc._remove_cached_provider(session.session_id)
    assert FakeProvider.instances[0].destroyed is True

    # Wipe in-memory history so we know the next turn really recovers from "DB"
    session.history = []

    await _drain(svc.streaming_reply_with_history(
        session=session, message="are you there", system_prompt="",
        history=[], tool_config={}, persist=False,
    ))

    assert len(FakeProvider.instances) == 2
    recovered = FakeProvider.instances[1]
    # The rebuilt provider was seeded with the persisted history
    assert recovered.init_history, "expected history recovered from DynamoDB"
    roles = [m["role"] for m in recovered.init_history]
    assert "user" in roles and "assistant" in roles


async def test_clear_history_destroys_provider_and_empties_db(svc, make_session):
    session = make_session(session_id="sid-clear", model_id="m1")

    await _drain(svc.streaming_reply_with_history(
        session=session, message="hi", system_prompt="",
        history=[], tool_config={}, persist=True,
    ))
    provider = FakeProvider.instances[0]

    await svc.clear_history(session)

    assert provider.destroyed is True
    assert session.history == []
    assert session.session_id not in svc._agent_cache


async def test_frontend_history_takes_precedence_over_db(svc, make_session):
    """If the caller passes history explicitly, we trust it over any DB copy."""
    session = make_session(session_id="sid-fe", model_id="m1")
    session._fake_db_history = [{"role": "user", "content": "stale-db-msg"}]

    frontend_history = [
        {"role": "user", "content": "fresh-frontend-msg"},
        {"role": "assistant", "content": "reply"},
    ]

    await _drain(svc.streaming_reply_with_history(
        session=session, message="next", system_prompt="",
        history=frontend_history, tool_config={}, persist=False,
    ))

    provider = FakeProvider.instances[0]
    init_texts = [
        m["content"][0]["text"] if isinstance(m["content"], list) else m["content"]
        for m in provider.init_history or []
    ]
    assert "fresh-frontend-msg" in init_texts
    assert "stale-db-msg" not in init_texts
