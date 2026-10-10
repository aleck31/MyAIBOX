"""Guards for third-party API drift (strands, mcp, smithy SDKs).

These caught real breakage when the dependencies were upgraded: modules that
import fine individually but fail at app start, or lazily-imported symbols that
were renamed. No network or AWS access needed.
"""
from __future__ import annotations

import os

import pytest

# Dummy config so importing the app doesn't need a real .env (a real one still wins).
os.environ.setdefault("USER_POOL_ID", "unit-test-pool")
os.environ.setdefault("CLIENT_ID", "unit-test-client")
os.environ.setdefault("SECRET_KEY", "unit-test-secret-key-0123456789abcdef0123456789")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")


def test_app_imports_and_registers_routes():
    import app

    paths = set(app.app.openapi()["paths"])  # HTTP routes; websockets aren't in the schema
    assert {"/health", "/api/upload", "/api/settings/mcp-servers"} <= paths


@pytest.mark.parametrize("config", [
    {"type": "stdio", "command": "echo", "args": []},
    {"type": "http", "url": "http://localhost:1/mcp"},
    {"type": "sse", "url": "http://localhost:1/sse"},
])
def test_every_mcp_transport_client_can_be_built(config):
    """Building (not connecting) imports each transport's client factory lazily."""
    from backend.genai.tools.provider import tool_provider

    class _Manager:
        def get_mcp_server_type(self, cfg):
            return cfg["type"]

    tool_provider._mcp_server_manager = _Manager()
    try:
        assert tool_provider._create_mcp_client(config) is not None
    finally:
        tool_provider._mcp_server_manager = None


# ── Talk event translation (strands.bidi event schema) ──────────────────────

def test_talk_transcript_deltas_accumulate_then_block_finalizes():
    from backend.api.talk import _to_frame

    state: dict = {}
    delta = lambda text: {"type": "bidi_transcript_delta", "delta": text, "role": "assistant", "content_id": "c1"}  # noqa: E731
    assert _to_frame(delta("Hel"), state) == {"type": "transcript", "text": "Hel", "role": "assistant", "final": False}
    assert _to_frame(delta("lo"), state)["text"] == "Hello"
    final = _to_frame({"type": "bidi_transcript_block", "transcript": "Hello!", "role": "assistant", "content_id": "c1"}, state)
    assert final == {"type": "transcript", "text": "Hello!", "role": "assistant", "final": True}
    assert state == {}  # turn closed, nothing leaks into the next one


def test_talk_transcripts_of_concurrent_turns_do_not_mix():
    from backend.api.talk import _to_frame

    state: dict = {}
    _to_frame({"type": "bidi_transcript_delta", "delta": "hi", "role": "user", "content_id": "u"}, state)
    out = _to_frame({"type": "bidi_transcript_delta", "delta": "yo", "role": "assistant", "content_id": "a"}, state)
    assert out["text"] == "yo"


def test_talk_audio_barge_in_and_ignored_events():
    from backend.api.talk import _to_frame

    audio = _to_frame({"type": "bidi_audio_delta", "audio": "AAAA", "sample_rate": 24000}, {})
    assert audio == {"type": "audio", "audio": "AAAA", "sample_rate": 24000}
    assert _to_frame({"type": "bidi_barge_in"}, {}) == {"type": "interrupted"}
    assert _to_frame({"type": "bidi_usage"}, {}) is None
    assert _to_frame("not-a-dict", {}) is None
