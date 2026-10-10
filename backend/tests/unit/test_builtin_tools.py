"""Built-in tool loading, in particular the local replacement for the deprecated current_time."""
from __future__ import annotations

import logging
import re
from datetime import datetime

import pytest

from backend.genai.tools.strands.builtin_tools import BUILTIN_TOOLS, get_available_tools, load_builtin_tools
from backend.genai.tools.strands.time_tool import current_time


def _call(**kwargs):
    # @tool functions stay directly callable
    return current_time(**kwargs)


def test_current_time_defaults_to_utc(monkeypatch):
    monkeypatch.delenv("DEFAULT_TIMEZONE", raising=False)
    value = _call()
    assert value.endswith("+00:00")
    datetime.fromisoformat(value)


def test_current_time_uses_default_timezone_env(monkeypatch):
    monkeypatch.setenv("DEFAULT_TIMEZONE", "Asia/Shanghai")
    assert _call().endswith("+08:00")


def test_current_time_explicit_timezone_wins(monkeypatch):
    monkeypatch.setenv("DEFAULT_TIMEZONE", "Asia/Shanghai")
    assert re.search(r"[+-]0[45]:00$", _call(timezone="America/New_York"))


def test_current_time_rejects_unknown_timezone():
    with pytest.raises(ValueError):
        _call(timezone="Mars/Olympus")


def test_current_time_loads_without_the_deprecated_strands_tool(caplog):
    tools = load_builtin_tools(["current_time"])
    assert len(tools) == 1 and getattr(tools[0], "__name__", "") == "backend.genai.tools.strands.time_tool"
    with caplog.at_level(logging.WARNING):
        _call()
    assert "deprecated" not in caplog.text.lower()


def test_every_builtin_tool_still_loads():
    assert set(get_available_tools()) == set(BUILTIN_TOOLS)
