"""OpenAI Responses tool loop: running out of tool rounds still produces an answer.

Regression: GPT-6.1 Sol kept searching until the round cap and the loop just ended, so Asking showed nothing at all.
"""
from __future__ import annotations

import types


from backend.genai.models.providers import openai_responses as orr  # noqa: E402


class _Item(dict):
    def model_dump(self):
        return dict(self)


def _tool_round(i):
    call = _Item(type="function_call", name="search_internet", call_id=f"c{i}", arguments="{}")
    return [types.SimpleNamespace(type="response.output_item.added", item=types.SimpleNamespace(type="function_call", call_id=f"c{i}", name="search_internet")),
            types.SimpleNamespace(type="response.completed", item=None, response=types.SimpleNamespace(output=[call]))]


def _answer():
    return [types.SimpleNamespace(type="response.output_text.delta", item=None, delta="final answer"),
            types.SimpleNamespace(type="response.completed", item=None, response=types.SimpleNamespace(output=[]))]


def test_out_of_tool_rounds_the_model_answers_with_tools_disabled(monkeypatch):
    monkeypatch.setattr(orr, "_MAX_TOOL_ROUNDS", 2)
    requests = []

    def create(**req):
        requests.append(dict(req))
        # A model that would keep calling tools for ever, unless tools are disabled
        return _answer() if req.get("tool_choice") == "none" else _tool_round(len(requests))

    provider = object.__new__(orr.OpenAIResponsesProvider)
    provider.model_id = "openai.gpt-6.1-sol"
    provider.llm_params = types.SimpleNamespace(max_tokens=1000, thinking=None)
    provider._tool_defs = [{"type": "function", "name": "search_internet"}]
    provider.client = types.SimpleNamespace(responses=types.SimpleNamespace(create=create))
    provider._exec_tool = lambda name, args: {"results": []}
    provider._convert_messages = lambda messages, system_prompt: []

    text = "".join((c.get("content") or {}).get("text", "") for c in provider.generate_stream([], ""))
    assert text == "final answer"
    assert len(requests) == 3 and requests[-1]["tool_choice"] == "none"
