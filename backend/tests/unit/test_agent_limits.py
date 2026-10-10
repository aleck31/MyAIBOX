"""Agent loop guard rails: a model stuck re-calling a tool must be stopped, not run for minutes."""
from __future__ import annotations

import os

os.environ.setdefault("USER_POOL_ID", "unit-test-pool")
os.environ.setdefault("CLIENT_ID", "unit-test-client")

from strands import Agent, tool  # noqa: E402
from strands.models import Model  # noqa: E402

from backend.genai.agents.limits import DEFAULT_MAX_CYCLES, CycleLimit, max_cycles_from_env  # noqa: E402


class LoopingModel(Model):
    """Always asks for the same tool, like a model that never accepts the tool result."""

    def __init__(self):
        self.calls = 0

    def update_config(self, **model_config):
        pass

    def get_config(self):
        return {}

    async def structured_output(self, *args, **kwargs):  # pragma: no cover - unused
        raise NotImplementedError

    async def stream(self, messages, tool_specs=None, system_prompt=None, **kwargs):
        self.calls += 1
        yield {"messageStart": {"role": "assistant"}}
        yield {"contentBlockStart": {"start": {"toolUse": {"toolUseId": f"call_{self.calls}", "name": "echo"}}}}
        yield {"contentBlockDelta": {"delta": {"toolUse": {"input": '{"text": "hi"}'}}}}
        yield {"contentBlockStop": {}}
        yield {"messageStop": {"stopReason": "tool_use"}}
        yield {"metadata": {"usage": {"inputTokens": 1, "outputTokens": 1, "totalTokens": 2}, "metrics": {"latencyMs": 1}}}


@tool
def echo(text: str) -> str:
    """Echo the text back."""
    return text


def _agent(max_calls):
    model = LoopingModel()
    return model, Agent(model=model, tools=[echo], callback_handler=None, hooks=[CycleLimit(max_calls, "loop")])


async def _run(agent, prompt="go"):
    async for _ in agent.stream_async(prompt):
        pass


async def test_looping_model_is_stopped_at_the_cap():
    model, agent = _agent(3)
    await _run(agent)
    assert model.calls == 3  # the 4th call was cancelled before reaching the model
    assert "Stopped after 3 model calls" in agent.messages[-1]["content"][0]["text"]


async def test_counter_resets_for_each_user_message():
    model, agent = _agent(2)
    await _run(agent, "first")
    await _run(agent, "second")
    assert model.calls == 4  # 2 + 2, not 2 then an immediate stop


def test_max_cycles_from_env(monkeypatch):
    monkeypatch.setenv("AGENT_MAX_CYCLES", "7")
    assert max_cycles_from_env() == 7
    for bad in ("", "abc", "0", "-5"):  # a bad value must not crash startup or disable the cap
        monkeypatch.setenv("AGENT_MAX_CYCLES", bad)
        assert max_cycles_from_env() == DEFAULT_MAX_CYCLES


async def test_agent_provider_tells_the_user_when_the_cap_stops_a_turn(monkeypatch):
    """Strands ends the turn with an assistant message it does not stream as text; the provider
    must emit it as a normal text chunk or the user sees a blank answer."""
    from backend.genai.agents.provider import AgentProvider

    monkeypatch.setenv("AGENT_MAX_CYCLES", "2")
    provider = AgentProvider(model_id="loop")
    monkeypatch.setattr(provider, "_get_strands_model", lambda *_: LoopingModel())
    monkeypatch.setattr(provider, "_load_tools", lambda: [echo])
    provider._cycle_limit.max_calls = 2

    chunks = [c async for c in provider.generate_stream("go")]
    texts = [c["text"] for c in chunks if isinstance(c.get("text"), str)]
    assert any("Stopped after 2 model calls" in t for t in texts), chunks
    assert not any(c.get("metadata", {}).get("error") for c in chunks)
