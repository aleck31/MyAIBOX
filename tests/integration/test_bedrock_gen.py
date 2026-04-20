"""End-to-end GenService / ChatService against real Bedrock.

Marked integration — excluded by default. Run with:
    uv run pytest -m integration tests/integration/test_bedrock_gen.py
"""
from __future__ import annotations

import pytest

from core.service.chat_service import ChatService
from core.service.gen_service import GenService
from genai.models.model_manager import model_manager

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module", autouse=True)
def _init_models():
    model_manager.init_default_models()


async def test_gen_text_stateless_returns_text():
    svc = GenService(module_name="Text")
    response = await svc.gen_text_stateless(
        content={"text": "Reply with exactly one word: OK"}
    )
    assert isinstance(response, str) and response.strip()


async def test_gen_text_with_session_persists(make_session):
    svc = GenService(module_name="Text")
    session = make_session(session_id="test-gen-session", module_name="Text")
    response = await svc.gen_text(
        session=session,
        content={"text": "Count to 3"},
    )
    assert response and isinstance(response, str)


async def test_gen_text_stream_yields_chunks(make_session):
    svc = GenService(module_name="Text")
    session = make_session(session_id="test-gen-stream-session", module_name="Text")
    chunks = []
    async for chunk in svc.gen_text_stream(
        session=session,
        content={"text": "List colors: red, green, blue"},
    ):
        chunks.append(chunk)
        if len(chunks) >= 5:
            break
    assert len(chunks) > 0


async def test_chat_service_streaming_reply(make_session):
    svc = ChatService(module_name="Persona")
    session = make_session(session_id="test-chat-session", module_name="Persona")
    chunks = []
    async for chunk in svc.streaming_reply(
        session=session,
        message={"text": "Say hi"},
        history=[],
        persist=False,
    ):
        chunks.append(chunk)
        if len(chunks) >= 5:
            break
    assert len(chunks) > 0
