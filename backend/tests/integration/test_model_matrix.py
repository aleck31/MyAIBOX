"""Model compatibility matrix: every enabled chat model, through both chains, thinking on and off.

Model support breaks in model-specific ways that no unit test can see (a parameter one model rejects, a
thinking format another renamed), and it used to surface only when a user hit it. This runs the real
calls instead, so a new or changed model is checked before it is registered or released.

    chain "provider": Text / Summary / Vision / Asking  (`create_model_provider(...).generate_stream`)
    chain "agent":    Chat                              (Strands `AgentProvider` calling a tool with an unguessable result)
    thinking on/off:  the module default vs. a user who turned thinking off (sampling params then apply)

Run (real AWS / Google calls, a couple of minutes):

    uv run pytest backend/tests/integration/test_model_matrix.py -m integration
    MODEL_MATRIX_ONLY="Opus,GPT-6" uv run pytest ...      # name / id substring filter
    MODEL_MATRIX_CANDIDATES=new_models.json uv run pytest ...

`MODEL_MATRIX_CANDIDATES` is a JSON list of model dicts (the registry format). They are tested in memory
only and never written to the registry, so a model can be vetted *before* it is added.

Provider-side overload, throttling or quota errors (503 "high demand", 429) are skipped, not failed:
they say nothing about this app.
"""
from __future__ import annotations

import asyncio
import concurrent.futures as cf
import json
import os
import re
import secrets
import time
from dataclasses import dataclass

import pytest
from strands import tool

from backend.genai.agents.provider import AgentProvider
from backend.genai.models import LLMMessage, LLMModel, LLMParameters
from backend.genai.models.model_manager import model_manager
from backend.genai.models.providers import create_model_provider

pytestmark = pytest.mark.integration

THINKING_ON = {"enabled": True, "effort": "high"}
WORKERS = 6
# Errors that describe the provider's capacity or our quota, not this app's request building.
TRANSIENT = re.compile(r"high demand|high load|exceeded your current quota|too many requests|throttl|overloaded|rate limit", re.I)
# Raw model control markup leaking into an answer means a field the model did not understand.
LEAK = re.compile(r"<\|[a-z_]+\|>|<call to=")


@dataclass
class Result:
    ok: bool
    detail: str
    transient: bool = False


def _is_chat_model(m: LLMModel) -> bool:
    return m.enabled and m.category in ("vision", "text") and bool(m.capabilities.tool_use)


def _models() -> list[LLMModel]:
    try:
        models = [m for m in model_manager.get_models() if _is_chat_model(m)]
    except Exception:  # no registry access: the tests below are reported as skipped
        models = []
    if path := os.getenv("MODEL_MATRIX_CANDIDATES"):
        with open(path, encoding="utf-8") as f:
            models += [LLMModel.from_dict(d) for d in json.load(f)]
    if only := [s.strip().lower() for s in os.getenv("MODEL_MATRIX_ONLY", "").split(",") if s.strip()]:
        models = [m for m in models if any(s in m.name.lower() or s in m.model_id.lower() for s in only)]
    return models


MODELS = _models()
CASES = [
    pytest.param(m, chain, think, id=f"{m.name}|{chain}|thinking-{'on' if think else 'off'}")
    for m in MODELS for chain in ("provider", "agent") for think in (True, False)
]


# ── the two chains ───────────────────────────────────────────────────────────

def _provider_chain(model: LLMModel, think: bool) -> Result:
    # Text-module style settings: sampling params present, thinking per module config.
    params = LLMParameters(max_tokens=4096, temperature=0.6, top_p=0.9, top_k=100, thinking=THINKING_ON if think else None)
    provider = create_model_provider(model.api_provider, model.model_id, params)
    text = ""
    for chunk in provider.generate_stream([LLMMessage(role="user", content="What is 17*23? Answer with just the number.")],
                                          system_prompt="Be concise."):
        text += chunk.get("content", {}).get("text", "")
    return Result("391" in text and not LEAK.search(text), f"answer={text.strip()[:80]!r}")


def _access_code_tool(code: str):
    @tool
    def get_access_code() -> str:
        """Return the access code. It is random, so the only way to know it is to call this tool."""
        return code
    return get_access_code


async def _agent_chain_async(model: LLMModel, think: bool) -> Result:
    # A random code the model cannot guess proves the tool call happened AND its result reached the answer
    # (asking for something it already knows, like the year, passes without any tool use).
    code = secrets.token_hex(3)
    params = {"max_tokens": 4096, "temperature": 0.7, "top_p": 0.9, "top_k": 100,
              "thinking": THINKING_ON if think else {"enabled": False}}
    agent = AgentProvider(model_id=model.model_id, system_prompt="Use the provided tools. Be concise.", parameters=params)
    agent._load_tools = lambda: [_access_code_tool(code)]  # skip registry-based tool loading; this tests the model
    text, tool_used, error = "", False, None
    try:
        async for chunk in agent.generate_stream("Call the get_access_code tool and reply with the exact code it returns."):
            if chunk.get("metadata", {}).get("error"):
                error = chunk.get("text")
            elif isinstance(chunk.get("text"), str):
                text += chunk["text"]
            if chunk.get("tool_use"):
                tool_used = True
    finally:
        agent.destroy()
    if error:
        return Result(False, str(error)[:300], transient=bool(TRANSIENT.search(str(error))))
    return Result(tool_used and code in text and not LEAK.search(text),
                  f"tool={tool_used} expected={code} answer={text.strip()[:80]!r}")


def _run(model: LLMModel, chain: str, think: bool) -> Result:
    try:
        return _provider_chain(model, think) if chain == "provider" else asyncio.run(_agent_chain_async(model, think))
    except Exception as e:
        # LLMProviderError's message is deliberately generic; the technical text is in .details
        detail = " | ".join(str(x) for x in (e, getattr(e, "details", None)) if x)[:300]
        return Result(False, f"{type(e).__name__}: {detail}", transient=bool(TRANSIENT.search(detail)))


def _run_with_retry(job) -> tuple[tuple, Result]:
    model, chain, think = job
    result = _run(model, chain, think)
    if not result.ok and result.transient:  # one more try before calling it overload
        time.sleep(5)
        result = _run(model, chain, think)
    return (model.model_id, chain, think), result


# ── tests ────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def matrix(request):
    """Run every selected combination concurrently, once, so per-case tests only look results up."""
    extra = {m.model_id: m for m in MODELS}
    patch = pytest.MonkeyPatch()
    real_lookup = model_manager.get_model_by_id
    patch.setattr(model_manager, "get_model_by_id", lambda mid: extra.get(mid) or real_lookup(mid))  # candidates stay in memory
    try:
        params = [item.callspec.params for item in request.session.items
                  if getattr(item, "originalname", "") == "test_model_works" and hasattr(item, "callspec")]
        jobs = [(p["model"], p["chain"], p["think"]) for p in params]
        with cf.ThreadPoolExecutor(WORKERS) as pool:
            yield dict(pool.map(_run_with_retry, jobs))
    finally:
        patch.undo()


@pytest.mark.skipif(not MODELS, reason="no chat models in the registry (or no registry access)")
@pytest.mark.parametrize("model,chain,think", CASES)
def test_model_works(matrix, model, chain, think):
    result = matrix[(model.model_id, chain, think)]
    if result.transient:
        pytest.skip(f"provider overloaded or over quota: {result.detail}")
    assert result.ok, f"{model.name} via the {chain} chain with thinking {'on' if think else 'off'}: {result.detail}"
