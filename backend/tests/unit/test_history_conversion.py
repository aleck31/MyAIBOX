"""AgentService history conversion — UI ↔ Strands.

Covers the data-shape translation without touching any Agent / LLM.
"""
from __future__ import annotations

from backend.core.service.agent_service import AgentService


def _svc() -> AgentService:
    # __new__ skips BaseService setup; we only exercise pure methods.
    return AgentService.__new__(AgentService)


def test_strands_to_ui_history_filters_tool_roles():
    svc = _svc()
    strands_msgs = [
        {"role": "system", "content": [{"text": "sys"}]},
        {"role": "tool", "content": [{"text": "tool out"}]},
        {"role": "user", "content": [{"text": "real"}]},
    ]
    out = svc._strands_to_ui_history(strands_msgs)
    assert out == [{"role": "user", "content": "real"}]


def test_a_request_with_no_answer_is_marked_as_stopped():
    """After Stop the frontend sent [old request, new request]: the model took the old one as pending and ran
    its tool again (a 10s sleep) before answering, and mixed both answers into the reply."""
    svc = _svc()
    out = svc._convert_to_strands_format([
        {"role": "user", "content": "sleep 10s then say done"},     # stopped: no reply was kept
        {"role": "user", "content": "say pong"},
        {"role": "assistant", "content": ""},                       # an empty reply is no answer either
    ])
    assert [m["role"] for m in out] == ["user", "assistant", "user", "assistant"]
    notes = [m["content"][0]["text"] for m in out if m["role"] == "assistant"]
    assert all("stopped" in n for n in notes)
