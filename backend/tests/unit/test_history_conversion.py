"""AgentService history conversion — UI ↔ Strands.

Covers the data-shape translation without touching any Agent / LLM.
"""
from __future__ import annotations

from backend.core.service.agent_service import AgentService


def _svc() -> AgentService:
    # __new__ skips BaseService setup; we only exercise pure methods.
    return AgentService.__new__(AgentService)


def test_convert_to_strands_format_handles_string_content():
    svc = _svc()
    ui = [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
    ]
    out = svc._convert_to_strands_format(ui)
    assert len(out) == 2
    assert out[0]["role"] == "user"
    assert out[0]["content"] == [{"text": "hi"}]
    assert out[1]["content"] == [{"text": "hello"}]


def test_convert_to_strands_format_unwraps_dict_content():
    svc = _svc()
    ui = [{"role": "user", "content": {"text": "hi", "files": ["a.png"]}}]
    out = svc._convert_to_strands_format(ui)
    # Only 'text' is preserved; files currently dropped by this converter
    assert out[0]["content"] == [{"text": "hi"}]


def test_convert_to_strands_format_skips_malformed_entries():
    svc = _svc()
    ui = [
        {"role": "user"},  # missing content
        {"content": "orphan"},  # missing role
        {"role": "user", "content": "ok"},
    ]
    out = svc._convert_to_strands_format(ui)
    assert len(out) == 1
    assert out[0]["content"] == [{"text": "ok"}]


def test_convert_to_strands_format_empty_returns_empty():
    assert _svc()._convert_to_strands_format([]) == []


def test_strands_to_ui_history_extracts_text_from_blocks():
    svc = _svc()
    strands_msgs = [
        {"role": "user", "content": [{"text": "hi"}]},
        {"role": "assistant", "content": [{"text": "hello"}, {"text": "world"}]},
    ]
    out = svc._strands_to_ui_history(strands_msgs)
    assert out == [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello\nworld"},
    ]


def test_strands_to_ui_history_filters_tool_roles():
    svc = _svc()
    strands_msgs = [
        {"role": "system", "content": [{"text": "sys"}]},
        {"role": "tool", "content": [{"text": "tool out"}]},
        {"role": "user", "content": [{"text": "real"}]},
    ]
    out = svc._strands_to_ui_history(strands_msgs)
    assert out == [{"role": "user", "content": "real"}]


def test_strands_to_ui_history_skips_empty_text():
    svc = _svc()
    strands_msgs = [
        {"role": "user", "content": [{"image": {"source": "..."}}]},
        {"role": "user", "content": [{"text": ""}]},
    ]
    out = svc._strands_to_ui_history(strands_msgs)
    assert out == []


def test_default_tool_config_shape():
    cfg = _svc()._get_default_tool_config()
    assert cfg["enabled"] is True
    assert cfg["mcp_tools_enabled"] is False
    assert cfg["strands_tools_enabled"] is True
    assert cfg["legacy_tools"] == []
