"""Asking answers survive a dropped connection: the client collects the same answer from /asking/resume."""
from __future__ import annotations

import os
import types

import pytest

os.environ.setdefault("USER_POOL_ID", "unit-test-pool")
os.environ.setdefault("CLIENT_ID", "unit-test-client")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from backend.api import asking, auth  # noqa: E402


@pytest.fixture
def client(monkeypatch):
    fake = types.SimpleNamespace(generate_stream=lambda **_: iter([{"content": {"text": "Bedrock is "}}, {"content": {"text": "a service."}}]))
    monkeypatch.setattr(asking, "_get_provider", lambda _mid: fake)
    app = FastAPI()
    app.include_router(asking.router, prefix="/api")
    app.dependency_overrides[auth.get_auth_user] = lambda: "user-1"
    return TestClient(app)


def _text(body: str) -> str:
    import json
    events = [json.loads(line[6:]) for line in body.split("\n") if line.startswith("data: ")]
    return "".join(e.get("delta", "") for e in events if e["type"] == "TEXT_MESSAGE_CONTENT")


def test_the_answer_can_be_collected_again_by_its_run_id(client):
    first = client.post("/api/asking/process", data={"text": "what is bedrock", "run_id": "r-1"}).text
    again = client.get("/api/asking/resume", params={"run_id": "r-1"})
    assert again.status_code == 200 and _text(again.text) == _text(first) == "Bedrock is a service."
    assert client.get("/api/asking/resume", params={"run_id": "unknown"}).status_code == 404


def test_two_answers_at_once_do_not_cancel_each_other(client):
    """Asking keeps no state, so a second question (another tab) must not stop the first."""
    client.post("/api/asking/process", data={"text": "a", "run_id": "r-a"})
    client.post("/api/asking/process", data={"text": "b", "run_id": "r-b"})
    assert _text(client.get("/api/asking/resume", params={"run_id": "r-a"}).text) == "Bedrock is a service."
    assert _text(client.get("/api/asking/resume", params={"run_id": "r-b"}).text) == "Bedrock is a service."
