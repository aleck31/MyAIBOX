"""Built-in tool loading, in particular the local replacement for the deprecated current_time."""
from __future__ import annotations

import logging
from datetime import datetime

import pytest

from backend.genai.tools.strands.builtin_tools import BUILTIN_TOOLS, get_available_tools, load_builtin_tools
from backend.genai.tools.strands.time_tool import current_time


def test_current_time_utc_by_default_and_explicit_timezone_wins(monkeypatch):
    monkeypatch.delenv("DEFAULT_TIMEZONE", raising=False)
    value = current_time()
    assert value.endswith("+00:00") and datetime.fromisoformat(value)
    assert current_time(timezone="Asia/Shanghai").endswith("+08:00")


def test_current_time_rejects_unknown_timezone():
    with pytest.raises(ValueError):
        current_time(timezone="Mars/Olympus")


def test_current_time_loads_without_the_deprecated_strands_tool(caplog):
    (loaded,) = load_builtin_tools(["current_time"])
    assert loaded.__name__ == "backend.genai.tools.strands.time_tool"
    with caplog.at_level(logging.WARNING):
        current_time()
    assert "deprecated" not in caplog.text.lower()


def test_every_builtin_tool_still_loads():
    assert set(get_available_tools()) == set(BUILTIN_TOOLS)
