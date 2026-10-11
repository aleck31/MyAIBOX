"""Session / SessionMetadata serialization round-trip."""
from __future__ import annotations

from datetime import datetime

from backend.core.session.models import Session, SessionMetadata


def test_session_round_trip_preserves_core_fields():
    original = Session(
        session_id="abc-123",
        session_name="unit test",
        created_time=datetime(2026, 1, 1, 12, 0, 0),
        updated_time=datetime(2026, 1, 1, 12, 30, 0),
        user_name="sub-uuid",
        metadata=SessionMetadata(module_name="assistant", model_id="claude-sonnet"),
        history=[{"role": "user", "content": {"text": "hi"}}],
    )
    restored = Session.from_dict(original.to_dict())

    assert restored.session_id == original.session_id
    assert restored.session_name == original.session_name
    assert restored.user_name == original.user_name
    assert restored.metadata.module_name == "assistant"
    assert restored.metadata.model_id == "claude-sonnet"
    assert restored.history == original.history


def test_to_dict_excludes_system_prompt_from_context():
    s = Session(
        session_id="x", session_name="x",
        created_time=datetime.now(), updated_time=datetime.now(),
        user_name="u", metadata=SessionMetadata(module_name="m"),
    )
    s.context["system_prompt"] = "secret prompt"
    assert "system_prompt" not in s.to_dict()["context"]
