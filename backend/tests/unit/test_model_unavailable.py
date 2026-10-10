"""A retired model id must give the user an actionable message, not a generic failure.

Regression: a page opened before a model was retired kept sending its old id, and Text answered
"An error occurred while processing your text." with the cause only in the log.
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
from backend.genai.models.model_manager import model_manager  # noqa: E402

OLD_ID = "openai.gpt-5.6-luna"
BODY = {"text": "hello", "operation": "rewrite", "model_id": OLD_ID}


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(text.router, prefix="/api")
    app.dependency_overrides[auth.get_auth_user] = lambda: "user-1"
    return TestClient(app)


def test_text_endpoint_names_the_unavailable_model(client, monkeypatch):
    monkeypatch.setattr(model_manager, "get_model_by_id", lambda _id: None)
    body = client.post("/api/text/process", json=BODY).text
    assert "RUN_ERROR" in body and OLD_ID in body and "refresh" in body.lower()


def test_other_failures_stay_generic_and_leak_nothing(client, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("provider exploded with secret detail")
    monkeypatch.setattr(model_manager, "get_model_by_id", boom)
    body = client.post("/api/text/process", json=BODY).text
    assert "An error occurred while processing your text" in body and "secret detail" not in body
