"""Per-model request parameters on both chains (provider chain + Strands agent chain).

Regression: models that reject temperature/top_p/top_k (new Claude, Grok 4.7, Kimi K3, GPT-5/6) failed
with HTTP 400 as soon as thinking was off; Gemini agents sent `max_tokens`, which google-genai's
GenerateContentConfig rejects.
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
THINK_OFF = {"enabled": False}


def _model(model_id, provider, vendor="Anthropic", **kw):
    return LLMModel(name=model_id, model_id=model_id, api_provider=provider, category="vision", vendor=vendor,
                    capabilities=CAPS, **kw)


@pytest.fixture
def registry(monkeypatch):
    models = {}
    monkeypatch.setattr(model_manager, "get_model_by_id", lambda mid: models.get(mid))
    monkeypatch.setenv("BEDROCK_SECRET_ID", "unit-secret")
    monkeypatch.setenv("GEMINI_SECRET_ID", "unit-gemini")
    monkeypatch.setattr(agent_module, "get_secret", lambda _id: {"api_key": "unit-key"})

    def add(model):
        models[model.model_id] = model
        return model.model_id
    return add


def _agent_model(model_id, **params):
    return AgentProvider(model_id=model_id, parameters={**SAMPLING, **params})._get_strands_model()


# ── agent chain: Bedrock ──────────────────────────────────────────────────────

@pytest.mark.parametrize("model_id", ["global.anthropic.claude-opus-5-5", "global.moonshotai.kimi-k3", "global.xai.grok-4.7"])
def test_agent_bedrock_omits_sampling_when_model_rejects_it(registry, model_id):
    cfg = _agent_model(registry(_model(model_id, "Bedrock")), thinking=THINK_OFF).get_config()
    assert "temperature" not in cfg and "top_p" not in cfg
    assert "top_k" not in (cfg.get("additional_request_fields") or {})
    assert cfg["max_tokens"] == 4096


def test_agent_bedrock_still_sends_sampling_to_models_that_accept_it(registry):
    cfg = _agent_model(registry(_model("global.anthropic.claude-sonnet-4-6", "Bedrock")), thinking=THINK_OFF).get_config()
    assert cfg["temperature"] == 0.7 and cfg["top_p"] == 0.9
    assert cfg["additional_request_fields"]["top_k"] == 100


def test_agent_bedrock_new_claude_uses_adaptive_thinking(registry):
    cfg = _agent_model(registry(_model("global.anthropic.claude-opus-5-5", "Bedrock")),
                       thinking={"enabled": True, "effort": "high"}).get_config()
    assert cfg["additional_request_fields"]["thinking"] == {"type": "adaptive", "display": "summarized"}


# ── agent chain: OpenAI Responses (Mantle) ────────────────────────────────────

def test_agent_responses_gpt_gets_no_temperature(registry):
    mid = registry(_model("openai.gpt-6.1-sol", "OpenAIResponses", "OpenAI"))
    assert "temperature" not in (_agent_model(mid, thinking=THINK_OFF).get_config().get("params") or {})


def test_agent_responses_non_gpt_keeps_temperature(registry):
    mid = registry(_model("xai.grok-4.3", "OpenAIResponses", "xAI"))
    assert _agent_model(mid, thinking=THINK_OFF).get_config()["params"]["temperature"] == 0.7


# ── agent chain: Gemini ───────────────────────────────────────────────────────

def test_agent_gemini_params_are_valid_generate_content_config(registry):
    from google.genai import types

    mid = registry(_model("gemini-3.8-flash", "Gemini", "Google"))
    params = _agent_model(mid).get_config()["params"]
    types.GenerateContentConfig(**params)  # raises on unknown fields such as `max_tokens`
    assert params["max_output_tokens"] == 4096 and params["temperature"] == 0.7


def test_agent_gemini_defaults_when_no_parameters(registry):
    mid = registry(_model("gemini-3.8-flash", "Gemini", "Google"))
    params = AgentProvider(model_id=mid)._get_strands_model().get_config()["params"]
    assert params["max_output_tokens"] == 8192


# ── provider chain (Text / Summary / Vision / Asking) ─────────────────────────

def _inference(model_id, thinking):
    provider = create_model_provider("Bedrock", model_id, LLMParameters(max_tokens=2000, temperature=0.6, top_p=0.9,
                                                                       top_k=100, thinking=thinking))
    return provider._prepare_inference_params()


@pytest.mark.parametrize("thinking", [None, {"enabled": True, "effort": "high"}])
def test_provider_chain_drops_sampling_for_restricted_claude(registry, thinking):
    mid = registry(_model("global.anthropic.claude-opus-5-5", "Bedrock"))
    inference, extra = _inference(mid, thinking)
    assert not {"temperature", "topP"} & set(inference)
    assert "top_k" not in (extra or {})
    if thinking:
        assert extra["thinking"]["type"] == "adaptive"


def test_provider_chain_drops_sampling_for_kimi_k3(registry):
    mid = registry(_model("global.moonshotai.kimi-k3", "Bedrock", "Moonshot AI"))
    inference, extra = _inference(mid, None)
    assert not {"temperature", "topP"} & set(inference) and "top_k" not in (extra or {})


def test_provider_chain_keeps_sampling_for_unrestricted_models(registry):
    mid = registry(_model("qwen.qwen3-vl-235b-a22b", "Bedrock", "Qwen"))
    inference, extra = _inference(mid, None)
    assert inference["temperature"] == 0.6 and inference["topP"] == 0.9
    assert extra == {"top_k": 100}


# ── seed list sanity ──────────────────────────────────────────────────────────

def test_default_models_are_unique_and_routable():
    from backend.genai.models.model_list import DEFAULT_MODELS

    ids = [m.model_id for m in DEFAULT_MODELS]
    assert len(ids) == len(set(ids))
    assert {m.api_provider for m in DEFAULT_MODELS} <= {"Bedrock", "BedrockInvoke", "BedrockSonic", "OpenAIResponses", "Gemini"}
    for m in DEFAULT_MODELS:
        if m.api_provider == "OpenAIResponses":
            assert m.base_url.startswith("https://bedrock-mantle."), m.model_id
        if m.api_provider == "Bedrock" and m.vendor in {"Anthropic", "xAI", "Z.AI", "Moonshot AI"}:
            assert m.model_id.startswith("global."), f"{m.model_id} needs a cross-Region inference profile"
