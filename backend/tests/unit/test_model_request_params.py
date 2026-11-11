"""Per-model request parameters on both chains (provider chain and Strands agent chain).

Regressions: models that reject temperature/top_p/top_k failed with HTTP 400 once thinking was off;
Gemini agents sent `max_tokens`, which GenerateContentConfig rejects; non-Claude models were sent
Claude's `thinking` field.
"""
from __future__ import annotations

import os
import types

import pytest
from botocore.exceptions import ClientError

# Importing the providers touches config; give them dummy values (a real .env still wins).
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")

from backend.genai.agents.provider import AgentProvider  # noqa: E402
from backend.genai.models import (  # noqa: E402
    API_BEDROCK_CONVERSE, API_GEMINI, API_OPENAI_RESPONSES, AUTH_API_KEY, AUTH_AWS,
    LLM_CAPABILITIES, LLMModel, LLMParameters, LLMProvider, VALID_APIS, clients,
)
from backend.genai.models.model_manager import model_manager  # noqa: E402
from backend.genai.models.provider_manager import provider_manager  # noqa: E402
from backend.genai.models.providers import create_model_provider  # noqa: E402
from backend.genai.models.providers import LLMProviderError  # noqa: E402
from backend.genai.models.providers.bedrock_converse import BedrockConverse  # noqa: E402
from backend.genai.models.providers.bedrock_invoke import BedrockInvoke  # noqa: E402

CAPS = LLM_CAPABILITIES(input_modality=["text"], output_modality=["text"], streaming=True, tool_use=True,
                        reasoning=True, context_window=100_000)
SAMPLING = {"max_tokens": 4096, "temperature": 0.7, "top_p": 0.9, "top_k": 100}
THINK_ON = {"enabled": True, "effort": "high"}
THINK_OFF = {"enabled": False}


@pytest.fixture
def registry(monkeypatch):
    """Register throwaway models: `add(model_id, provider, vendor, api)` returns the id."""
    models = {}
    providers = {p.name: p for p in (
        LLMProvider(name="aws", auth=AUTH_AWS, region="us-west-2", apis=[API_BEDROCK_CONVERSE]),
        LLMProvider(name="google", auth=AUTH_API_KEY, api_key="unit-key", apis=[API_GEMINI]),
        LLMProvider(name="gw", auth=AUTH_API_KEY, api_key="unit-key", base_url="https://gw.example",
                    apis=[a for a in VALID_APIS if a != "bedrock-bidi-stream"]),
    )}
    monkeypatch.setattr(model_manager, "get_model_by_id", lambda mid: models.get(mid))
    monkeypatch.setattr(provider_manager, "get_provider", lambda name: providers.get(name))

    def add(model_id, provider="aws", vendor="Anthropic", api=None):
        api = api or (API_GEMINI if provider == "google" else API_BEDROCK_CONVERSE)
        models[model_id] = LLMModel(name=model_id, model_id=model_id, provider=provider, api=api, category="vision",
                                    vendor=vendor, capabilities=CAPS)
        return model_id
    return add


def _agent_config(model_id, **params):
    return AgentProvider(model_id=model_id, parameters={**SAMPLING, **params})._get_strands_model().get_config()


def _fields(cfg):
    return cfg.get("additional_request_fields") or {}


# ── agent chain (Chat) ────────────────────────────────────────────────────────

@pytest.mark.parametrize("model_id,vendor", [("global.anthropic.claude-opus-5-5", "Anthropic"),
                                             ("global.moonshotai.kimi-k3", "Moonshot AI")])
def test_agent_omits_sampling_for_models_that_reject_it(registry, model_id, vendor):
    cfg = _agent_config(registry(model_id, vendor=vendor), thinking=THINK_OFF)
    assert "temperature" not in cfg and "top_p" not in cfg and "top_k" not in _fields(cfg)


def test_agent_gemini_params_are_a_valid_generate_content_config(registry):
    from google.genai import types

    params = _agent_config(registry("gemini-3.8-flash", "google", "Google"))["params"]
    types.GenerateContentConfig(**params)  # raises on unknown fields such as `max_tokens`
    assert params["max_output_tokens"] == 4096


@pytest.mark.parametrize("model_id,vendor", [("global.amazon.nova-2-lite-v1:0", "Amazon"), ("openai.gpt-oss-120b-1:0", "OpenAI")])
def test_agent_sends_no_claude_thinking_field_to_other_vendors(registry, model_id, vendor):
    assert "thinking" not in _fields(_agent_config(registry(model_id, vendor=vendor), thinking=THINK_ON))


# ── provider chain (Text / Summary / Vision / Asking) ─────────────────────────

@pytest.mark.parametrize("model_id,thinking,restricted", [
    ("global.anthropic.claude-opus-5-5", None, True),
    ("global.anthropic.claude-opus-5-5", THINK_ON, True),
    ("qwen.qwen3-vl-235b-a22b", None, False),
])
def test_provider_chain_sampling(registry, model_id, thinking, restricted):
    mid = registry(model_id)
    params = LLMParameters(max_tokens=2000, temperature=0.6, top_p=0.9, top_k=100, thinking=thinking)
    inference, extra = create_model_provider(API_BEDROCK_CONVERSE, mid, params)._prepare_inference_params()
    assert bool({"temperature", "topP"} & set(inference) or "top_k" in (extra or {})) != restricted
    if thinking:
        assert extra["thinking"]["type"] == "adaptive"


# ── seed list ─────────────────────────────────────────────────────────────────

def test_default_models_are_unique_and_routable():
    from backend.genai.models.model_list import DEFAULT_MODELS, DEFAULT_PROVIDERS

    ids = [m.model_id for m in DEFAULT_MODELS]
    assert len(ids) == len(set(ids))
    providers = {p.name: p for p in DEFAULT_PROVIDERS}
    for m in DEFAULT_MODELS:
        assert m.api in providers[m.provider].apis, f"{m.model_id}: {m.provider} does not serve {m.api}"
        if m.api == API_BEDROCK_CONVERSE and m.vendor in {"Anthropic", "xAI", "Z.AI", "Moonshot AI"}:
            assert m.model_id.startswith("global."), f"{m.model_id} needs a cross-Region inference profile"


# ── providers ─────────────────────────────────────────────────────────────────

def test_model_calls_go_to_the_provider_endpoint_with_its_key(registry):
    """agw rejects x-api-key and SigV4: every API must send the provider key as a Bearer token to its URL."""
    gw = provider_manager.get_provider("gw")
    assert clients.openai_client_args(gw) == {"api_key": "unit-key", "base_url": "https://gw.example/v1"}
    client = BedrockConverse(registry("global.anthropic.claude-sonnet-5-5", "gw"), LLMParameters()).client
    assert client.meta.endpoint_url == "https://gw.example"
    request = types.SimpleNamespace(headers={})
    client.meta.events.emit("before-send.bedrock-runtime.Converse", request=request)
    assert request.headers["Authorization"] == "Bearer unit-key"


def test_provider_edit_rebuilds_cached_clients(registry, monkeypatch):
    """A rotated key or new URL must reach cached Chat agents and Asking providers, not wait for a restart."""
    monkeypatch.setattr(provider_manager, "_cache", [])
    agent = AgentProvider(model_id=registry("global.anthropic.claude-sonnet-5-5", "gw"))
    agent._get_strands_model()
    assert not agent.model_outdated
    provider_manager.flush_cache()
    assert agent.model_outdated


@pytest.mark.parametrize("base_url,expected", [
    ("https://gw.example", "https://gw.example/v1"),
    ("https://bedrock-mantle.us-east-1.api.aws/openai/v1", "https://bedrock-mantle.us-east-1.api.aws/openai/v1"),
    ("https://generativelanguage.googleapis.com/v1beta/openai/", "https://generativelanguage.googleapis.com/v1beta/openai"),
])
def test_openai_base_url_gets_v1_only_on_a_bare_host(base_url, expected):
    p = LLMProvider(name="x", auth=AUTH_API_KEY, api_key="k", base_url=base_url, apis=["openai-responses"])
    assert clients.openai_client_args(p)["base_url"] == expected


@pytest.mark.parametrize("raw", ['{"api_key": "k1"}', "{'api_key': 'k1'}", "k1\n"])
def test_secret_formats(raw):
    assert clients._key_from_secret(raw) == "k1"


def test_model_on_a_provider_without_its_api_is_refused(registry):
    mid = registry("gpt-6.1-sol", "aws", api=API_OPENAI_RESPONSES)
    with pytest.raises(ValueError, match="does not serve"):
        AgentProvider(model_id=mid)._get_strands_model()


def test_provider_key_is_never_returned_and_kept_on_edit(monkeypatch):
    from backend.api import settings as api

    monkeypatch.setattr(model_manager, "get_models", lambda **_: [])
    stored = LLMProvider(name="gw", auth=AUTH_API_KEY, api_key="secret-key", apis=[API_OPENAI_RESPONSES])
    assert "secret-key" not in str(api._provider_view(stored))
    body = api.ProviderRequest(name="gw", auth=AUTH_API_KEY, apis=[API_OPENAI_RESPONSES], base_url="https://gw.example")
    assert api._provider_from_request(body, stored).api_key == "secret-key"


def test_provider_writes_are_admin_only(monkeypatch):
    from backend.api import settings as api

    monkeypatch.setattr(api, "is_admin", lambda sub: sub == "admin")
    assert api._provider_write_denied("someone").status_code == 403
    assert api._provider_write_denied("admin") is None


# ── Chat: stop sequences and mid-conversation model switches ──────────────────

@pytest.mark.parametrize("model_id,vendor,sent", [
    ("deepseek.v3.2", "DeepSeek", False), ("qwen.qwen3-vl-235b-a22b", "Qwen", False),
    ("global.anthropic.claude-sonnet-4-6", "Anthropic", True),
])
def test_agent_sends_stop_sequences_only_to_models_that_accept_them(registry, model_id, vendor, sent):
    cfg = _agent_config(registry(model_id, vendor=vendor), thinking=THINK_OFF, stop_sequences=["end_turn"])
    assert ("stop_sequences" in cfg) == sent


def test_switching_model_drops_reasoning_blocks_from_history(registry):
    """Claude's signed reasoning in the history made most other models answer HTTP 400 after a switch."""
    provider = AgentProvider(model_id=registry("global.anthropic.claude-haiku-5-5"))
    provider._agent = provider._ensure_agent()
    provider._agent.messages[:] = [
        {"role": "user", "content": [{"text": "12*13?"}]},
        {"role": "assistant", "content": [{"reasoningContent": {"reasoningText": {"text": "…", "signature": "sig"}}},
                                          {"text": "156"}]},
    ]
    provider.update_model(registry("qwen.qwen3-vl-235b-a22b", vendor="Qwen"))
    assert provider.messages[1]["content"] == [{"text": "156"}]
    assert provider.messages[0]["content"] == [{"text": "12*13?"}]


@pytest.mark.parametrize("provider_cls", [BedrockInvoke, BedrockConverse])
def test_retired_bedrock_model_gets_an_actionable_message(provider_cls):
    """AWS answers ResourceNotFoundException for models it retired; 'Please try again' would be wrong."""
    err = ClientError({"Error": {"Code": "ResourceNotFoundException", "Message": "Legacy model"}}, "InvokeModel")
    with pytest.raises(LLMProviderError) as raised:
        provider_cls._handle_bedrock_error(object.__new__(provider_cls), err)
    assert "choose another model" in raised.value.message.lower()
    assert "try again" not in raised.value.message.lower()


def test_converse_tool_loop_is_capped(monkeypatch):
    """With search failing, Claude kept calling it (18 calls, minutes). Past the cap it is told to answer, then stopped."""
    from backend.genai.models.providers import bedrock_converse as bc
    monkeypatch.setattr(bc, "MAX_TOOL_ROUNDS", 2)

    async def fake_execute(name, **kw):
        return {"error": "search failed"}
    monkeypatch.setattr(bc.legacy_tool_registry, "execute_tool", fake_execute)
    provider = object.__new__(BedrockConverse)
    provider.llm_params = types.SimpleNamespace(thinking=None)
    provider._convert_messages = lambda messages: []
    sent = []

    def always_a_tool(messages, **_):
        sent.append([m for m in messages])
        yield {"role": "assistant", "tool_use": {"toolUseId": f"t{len(sent)}", "name": "search_internet", "input": {"query": "x"}}}
    provider._converse_stream_sync = always_a_tool

    text = "".join((c.get("content") or {}).get("text", "") for c in provider.generate_stream(messages=[], system_prompt=""))
    assert len(sent) == 3                                    # 2 rounds, the "answer now" round, then it stops
    assert any("answer now" in b.get("text", "") for b in sent[2][-1]["content"])
    assert "Stopped after too many tool calls" in text
