"""Per-model request parameters on both chains (provider chain and Strands agent chain).

Regressions: models that reject temperature/top_p/top_k failed with HTTP 400 once thinking was off;
Gemini agents sent `max_tokens`, which GenerateContentConfig rejects; non-Claude models were sent
Claude's `thinking` field.
"""
from __future__ import annotations

import os

import pytest

# Importing the providers touches config; give them dummy values (a real .env still wins).
os.environ.setdefault("USER_POOL_ID", "unit-test-pool")
os.environ.setdefault("CLIENT_ID", "unit-test-client")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")

from backend.genai.agents import provider as agent_module  # noqa: E402
from backend.genai.agents.provider import AgentProvider  # noqa: E402
from backend.genai.models import LLM_CAPABILITIES, LLMModel, LLMParameters  # noqa: E402
from backend.genai.models.model_manager import model_manager  # noqa: E402
from backend.genai.models.providers import create_model_provider  # noqa: E402

CAPS = LLM_CAPABILITIES(input_modality=["text"], output_modality=["text"], streaming=True, tool_use=True,
                        reasoning=True, context_window=100_000)
SAMPLING = {"max_tokens": 4096, "temperature": 0.7, "top_p": 0.9, "top_k": 100}
THINK_ON = {"enabled": True, "effort": "high"}
THINK_OFF = {"enabled": False}


@pytest.fixture
def registry(monkeypatch):
    """Register throwaway models: `add(model_id, provider, vendor)` returns the id."""
    models = {}
    monkeypatch.setattr(model_manager, "get_model_by_id", lambda mid: models.get(mid))
    monkeypatch.setenv("BEDROCK_SECRET_ID", "unit-secret")
    monkeypatch.setenv("GEMINI_SECRET_ID", "unit-gemini")
    monkeypatch.setattr(agent_module, "get_secret", lambda _id: {"api_key": "unit-key"})

    def add(model_id, provider="Bedrock", vendor="Anthropic"):
        models[model_id] = LLMModel(name=model_id, model_id=model_id, api_provider=provider, category="vision",
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


def test_agent_still_sends_sampling_to_models_that_accept_it(registry):
    cfg = _agent_config(registry("global.anthropic.claude-sonnet-4-6"), thinking=THINK_OFF)
    assert cfg["temperature"] == 0.7 and _fields(cfg)["top_k"] == 100


def test_agent_new_claude_uses_adaptive_thinking(registry):
    cfg = _agent_config(registry("global.anthropic.claude-opus-5-5"), thinking=THINK_ON)
    assert _fields(cfg)["thinking"] == {"type": "adaptive", "display": "summarized"}


@pytest.mark.parametrize("model_id,vendor,sends_temperature", [("openai.gpt-6.1-sol", "OpenAI", False),
                                                               ("xai.grok-4.3", "xAI", True)])
def test_agent_responses_models_temperature(registry, model_id, vendor, sends_temperature):
    cfg = _agent_config(registry(model_id, "OpenAIResponses", vendor), thinking=THINK_OFF)
    assert ("temperature" in (cfg.get("params") or {})) == sends_temperature


def test_agent_gemini_params_are_a_valid_generate_content_config(registry):
    from google.genai import types

    params = _agent_config(registry("gemini-3.8-flash", "Gemini", "Google"))["params"]
    types.GenerateContentConfig(**params)  # raises on unknown fields such as `max_tokens`
    assert params["max_output_tokens"] == 4096


@pytest.mark.parametrize("model_id,vendor", [("global.amazon.nova-2-lite-v1:0", "Amazon"), ("openai.gpt-oss-120b-1:0", "OpenAI")])
def test_agent_sends_no_claude_thinking_field_to_other_vendors(registry, model_id, vendor):
    assert "thinking" not in _fields(_agent_config(registry(model_id, vendor=vendor), thinking=THINK_ON))


def test_agent_top_k_is_named_per_family(registry):
    def top_k(model_id, vendor):
        return _fields(_agent_config(registry(model_id, vendor=vendor), thinking=THINK_OFF))
    assert top_k("global.amazon.nova-2-lite-v1:0", "Amazon") == {"inferenceConfig": {"topK": 100}}
    assert top_k("deepseek.v3.2", "DeepSeek") == {}
    assert top_k("global.zai.glm-5.3", "Z.AI") == {"top_k": 100}


# ── provider chain (Text / Summary / Vision / Asking) ─────────────────────────

@pytest.mark.parametrize("model_id,thinking,restricted", [
    ("global.anthropic.claude-opus-5-5", None, True),
    ("global.anthropic.claude-opus-5-5", THINK_ON, True),
    ("qwen.qwen3-vl-235b-a22b", None, False),
])
def test_provider_chain_sampling(registry, model_id, thinking, restricted):
    mid = registry(model_id)
    params = LLMParameters(max_tokens=2000, temperature=0.6, top_p=0.9, top_k=100, thinking=thinking)
    inference, extra = create_model_provider("Bedrock", mid, params)._prepare_inference_params()
    assert bool({"temperature", "topP"} & set(inference) or "top_k" in (extra or {})) != restricted
    if thinking:
        assert extra["thinking"]["type"] == "adaptive"


# ── seed list ─────────────────────────────────────────────────────────────────

def test_default_models_are_unique_and_routable():
    from backend.genai.models.model_list import DEFAULT_MODELS

    ids = [m.model_id for m in DEFAULT_MODELS]
    assert len(ids) == len(set(ids))
    for m in DEFAULT_MODELS:
        if m.api_provider == "OpenAIResponses":
            assert m.base_url.startswith("https://bedrock-mantle."), m.model_id
        if m.api_provider == "Bedrock" and m.vendor in {"Anthropic", "xAI", "Z.AI", "Moonshot AI"}:
            assert m.model_id.startswith("global."), f"{m.model_id} needs a cross-Region inference profile"


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
