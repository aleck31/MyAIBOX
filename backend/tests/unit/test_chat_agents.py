"""ChatAgentRegistry — merge of built-in definitions + per-user overrides.

The DDB table is mocked end-to-end so the test runs offline. We only
exercise the public contract: list / get / set_override / reset, plus
the overridable-field whitelist.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from backend.api.prompts.chat import BUILTIN_AGENTS


@pytest.fixture
def registry(monkeypatch):
    """A ChatAgentRegistry with the DDB table stubbed out."""
    from backend.core import chat_agents

    reg = chat_agents.ChatAgentRegistry.__new__(chat_agents.ChatAgentRegistry)
    reg.table = MagicMock()
    reg._cache = {}

    # In-memory "DDB": {partition_key_tuple: item_dict}
    store: dict = {}

    def get_item(Key):
        k = (Key["setting_name"], Key["type"])
        return {"Item": store[k]} if k in store else {}

    def put_item(Item):
        k = (Item["setting_name"], Item["type"])
        store[k] = Item

    reg.table.get_item.side_effect = get_item
    reg.table.put_item.side_effect = put_item
    return reg


def test_set_override_silently_drops_non_overridable_fields(registry):
    resolved = registry.set_override(
        "alice", "assistant",
        {"parameters": {"temperature": 0.1}, "name": "Hacked", "prompt": "evil"},
    )
    assert resolved.name == BUILTIN_AGENTS["assistant"].name
    assert resolved.prompt == BUILTIN_AGENTS["assistant"].prompt


def test_overrides_are_per_user(registry):
    registry.set_override("alice", "assistant", {"parameters": {"temperature": 0.1}})
    assert registry.get_agent("bob", "assistant").parameters == BUILTIN_AGENTS["assistant"].parameters
    assert registry.get_agent("alice", "assistant").parameters == {"temperature": 0.1}


def test_reset_drops_override(registry):
    registry.set_override("alice", "assistant", {"parameters": {"temperature": 0.2}})
    registry.reset("alice", "assistant")
    got = registry.get_agent("alice", "assistant")
    assert got.parameters == BUILTIN_AGENTS["assistant"].parameters


def test_returned_agents_do_not_leak_override_mutation(registry):
    """Mutating a returned Agent's list field must not corrupt the stored override."""
    registry.set_override("alice", "assistant", {"enabled_skills": ["a"]})
    got = registry.get_agent("alice", "assistant")
    got.enabled_skills.append("b")  # attacker mutates
    fresh = registry.get_agent("alice", "assistant")
    assert fresh.enabled_skills == ["a"]
