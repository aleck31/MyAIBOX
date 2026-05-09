"""ChatAgentRegistry — merge of built-in definitions + per-user overrides.

The DDB table is mocked end-to-end so the test runs offline. We only
exercise the public contract: list / get / set_override / reset, plus
the overridable-field whitelist.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from backend.api.prompts.chat import BUILTIN_AGENTS, Agent, OVERRIDABLE_FIELDS


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


def test_list_agents_returns_all_builtins(registry):
    agents = registry.list_agents("alice")
    assert {a.id for a in agents} == set(BUILTIN_AGENTS.keys())


def test_get_agent_with_no_override_returns_builtin(registry):
    got = registry.get_agent("alice", "assistant")
    builtin = BUILTIN_AGENTS["assistant"]
    assert got.name == builtin.name
    assert got.enabled_legacy_tools == builtin.enabled_legacy_tools
    assert got.parameters == builtin.parameters


def test_get_unknown_agent_raises(registry):
    with pytest.raises(KeyError):
        registry.get_agent("alice", "does-not-exist")


def test_set_override_merges_into_builtin(registry):
    resolved = registry.set_override(
        "alice", "assistant",
        {"parameters": {"temperature": 0.1}},
    )
    assert resolved.parameters == {"temperature": 0.1}
    # Name / prompt / avatar remain the built-in values
    assert resolved.name == BUILTIN_AGENTS["assistant"].name
    assert resolved.prompt == BUILTIN_AGENTS["assistant"].prompt


def test_set_override_silently_drops_non_overridable_fields(registry):
    resolved = registry.set_override(
        "alice", "assistant",
        {"parameters": {"temperature": 0.1}, "name": "Hacked", "prompt": "evil"},
    )
    assert resolved.name == BUILTIN_AGENTS["assistant"].name
    assert resolved.prompt == BUILTIN_AGENTS["assistant"].prompt


def test_set_override_unknown_agent_raises(registry):
    with pytest.raises(KeyError):
        registry.set_override("alice", "ghost", {"parameters": {}})


def test_override_persists_across_get_calls(registry):
    registry.set_override("alice", "assistant", {"parameters": {"temperature": 0.2}})
    # Drop the in-process cache to force a reload from the mocked DDB
    registry.invalidate("alice")
    got = registry.get_agent("alice", "assistant")
    assert got.parameters["temperature"] == 0.2


def test_overrides_are_per_user(registry):
    registry.set_override("alice", "assistant", {"parameters": {"temperature": 0.1}})
    assert registry.get_agent("bob", "assistant").parameters == BUILTIN_AGENTS["assistant"].parameters
    assert registry.get_agent("alice", "assistant").parameters == {"temperature": 0.1}


def test_set_override_is_additive(registry):
    registry.set_override("alice", "assistant", {"parameters": {"temperature": 0.2}})
    resolved = registry.set_override("alice", "assistant", {"enabled_skills": ["foo"]})
    assert resolved.parameters == {"temperature": 0.2}
    assert resolved.enabled_skills == ["foo"]


def test_reset_drops_override(registry):
    registry.set_override("alice", "assistant", {"parameters": {"temperature": 0.2}})
    registry.reset("alice", "assistant")
    got = registry.get_agent("alice", "assistant")
    assert got.parameters == BUILTIN_AGENTS["assistant"].parameters


def test_reset_unknown_agent_raises(registry):
    with pytest.raises(KeyError):
        registry.reset("alice", "ghost")


def test_returned_agents_do_not_leak_override_mutation(registry):
    """Mutating a returned Agent's list field must not corrupt the stored override."""
    registry.set_override("alice", "assistant", {"enabled_skills": ["a"]})
    got = registry.get_agent("alice", "assistant")
    got.enabled_skills.append("b")  # attacker mutates
    fresh = registry.get_agent("alice", "assistant")
    assert fresh.enabled_skills == ["a"]


def test_overridable_fields_matches_agent_dataclass():
    """Every key in the whitelist must exist as a field on Agent — any
    drift would silently let set_override drop a legitimate patch."""
    field_names = {f for f in Agent.__dataclass_fields__}
    assert OVERRIDABLE_FIELDS <= field_names


def test_agent_is_immutable_enough(registry):
    """Agent is a regular dataclass — list/dict fields are mutable by design,
    but the built-in constants must survive an attacker mutating a returned
    copy. Covered by test_returned_agents_do_not_leak_override_mutation.
    This test asserts the base constant itself isn't mutated via get_agent."""
    original_skills = list(BUILTIN_AGENTS["assistant"].enabled_skills)
    got = registry.get_agent("alice", "assistant")
    got.enabled_skills.append("hack")
    assert BUILTIN_AGENTS["assistant"].enabled_skills == original_skills


def test_agent_dataclass_fields_are_complete():
    """Quick audit: every overridable field actually exists on Agent."""
    field_names = {f for f in Agent.__dataclass_fields__}
    missing = OVERRIDABLE_FIELDS - field_names
    assert not missing, f"OVERRIDABLE_FIELDS references unknown fields: {missing}"
