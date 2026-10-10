"""A retired/unknown model id must produce a message the user can act on, not a generic failure.

Regression: after models were retired, a page opened beforehand kept sending the old id and
Text only said "An error occurred while processing your text."
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("USER_POOL_ID", "unit-test-pool")
os.environ.setdefault("CLIENT_ID", "unit-test-client")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from backend.api import auth, text  # noqa: E402
from backend.common.errors import ModelUnavailableError, user_message  # noqa: E402
from backend.genai.models.model_manager import model_manager  # noqa: E402

OLD_ID = "openai.gpt-5.6-luna"


def test_message_names_the_model_and_tells_the_user_what_to_do():
    msg = str(ModelUnavailableError(OLD_ID))
    assert OLD_ID in msg and "not available" in msg and "refresh" in msg.lower()


def test_still_a_value_error_for_existing_handlers():
    assert isinstance(ModelUnavailableError("x"), ValueError)


def test_user_message_exposes_only_user_facing_errors():
    assert OLD_ID in user_message(ModelUnavailableError(OLD_ID), "generic")
    assert user_message(RuntimeError("boto3 stack detail"), "generic") == "generic"
    assert user_message(ValueError("Model not found: x"), "generic") == "generic"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(model_manager, "get_model_by_id", lambda _id: None)  # nothing is registered
    app = FastAPI()
    app.include_router(text.router, prefix="/api")
    app.dependency_overrides[auth.get_auth_user] = lambda: "user-1"
    return TestClient(app)


def test_text_endpoint_reports_the_unavailable_model(client):
    resp = client.post("/api/text/process", json={"text": "hello", "operation": "rewrite", "model_id": OLD_ID})
    body = resp.text
    assert "RUN_ERROR" in body
    assert OLD_ID in body and "not available" in body
    assert "An error occurred while processing your text" not in body


def test_text_endpoint_keeps_generic_message_for_other_failures(client, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("provider exploded with secret detail")

    monkeypatch.setattr(model_manager, "get_model_by_id", boom)
    resp = client.post("/api/text/process", json={"text": "hello", "operation": "rewrite", "model_id": OLD_ID})
    assert "An error occurred while processing your text" in resp.text
    assert "secret detail" not in resp.text


# ── every "model not found" site raises the user-facing error ─────────────────

def _raises_unavailable(call):
    with pytest.raises(ModelUnavailableError) as exc:
        call()
    assert exc.value.model_id == OLD_ID


@pytest.fixture
def empty_registry(monkeypatch):
    monkeypatch.setattr(model_manager, "get_model_by_id", lambda _id: None)


def test_vision_and_asking_providers(empty_registry):
    from backend.api import asking, vision

    _raises_unavailable(lambda: vision._get_provider(OLD_ID))
    _raises_unavailable(lambda: asking._get_provider(OLD_ID))


def test_service_layer_text_provider(empty_registry):
    from backend.core.service.service_factory import ServiceFactory

    service = ServiceFactory.create_gen_service("text")
    _raises_unavailable(lambda: service._get_model_provider(OLD_ID))


def test_agent_chain(empty_registry):
    from backend.genai.agents.provider import AgentProvider

    _raises_unavailable(lambda: AgentProvider(model_id=OLD_ID)._get_strands_model())


def test_openai_responses_provider_does_not_bury_the_error(empty_registry):
    from backend.genai.models import LLMParameters
    from backend.genai.models.providers import create_model_provider

    _raises_unavailable(lambda: create_model_provider("OpenAIResponses", OLD_ID, LLMParameters()))
