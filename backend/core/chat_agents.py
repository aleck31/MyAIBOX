"""Chat agent registry with per-user overrides.

The canonical agent definitions live in
:mod:`backend.api.prompts.chat` as Python constants. Users can tweak
the mutable fields (``default_model``, the four ``enabled_*`` lists,
``parameters``) per-agent; overrides are persisted in DynamoDB under a
per-user partition and merged on top of the built-in definition at
read time.

Read path::

    builtin_agent = BUILTIN_AGENTS[id]
    overrides = load_user_overrides(user_id).get(id, {})
    resolved = dataclasses.replace(builtin_agent, **overrides)

Write path: PATCH body → validated against ``OVERRIDABLE_FIELDS`` →
persisted into the user's overrides doc. Reset deletes the entry.
"""
from __future__ import annotations

import copy
from dataclasses import replace
from decimal import Decimal
from typing import Any, Dict

from backend.api.prompts.chat import Agent, BUILTIN_AGENTS, OVERRIDABLE_FIELDS
from backend.common.logger import logger
from backend.core.config import env_config
from backend.utils.aws import get_aws_session


DDB_SETTING_NAME = "agent_overrides"


class ChatAgentRegistry:
    def __init__(self):
        session = get_aws_session(region_name=env_config.aws_region)
        dynamodb = session.resource("dynamodb")
        table_method = getattr(dynamodb, "Table")
        self.table = table_method(env_config.database_config["setting_table"])
        # In-process cache of overrides per user. Cleared on write.
        self._cache: Dict[str, Dict[str, Dict]] = {}

    # ── Override IO ─────────────────────────────────────────────────────

    def _ddb_key(self, user_id: str) -> Dict[str, str]:
        return {"setting_name": DDB_SETTING_NAME, "type": f"user:{user_id}"}

    def _load_overrides(self, user_id: str) -> Dict[str, Dict]:
        if user_id in self._cache:
            return self._cache[user_id]
        try:
            resp = self.table.get_item(Key=self._ddb_key(user_id))
        except Exception as e:
            logger.error(f"[ChatAgents] load failed for {user_id}: {e}", exc_info=True)
            return {}
        item = resp.get("Item") or {}
        raw = item.get("overrides", {})
        overrides = _from_ddb(raw) if raw else {}
        self._cache[user_id] = overrides
        return overrides

    def _save_overrides(self, user_id: str, overrides: Dict[str, Dict]) -> None:
        self.table.put_item(Item={
            **self._ddb_key(user_id),
            "overrides": _to_ddb(overrides),
        })
        self._cache[user_id] = overrides

    # ── Public API ──────────────────────────────────────────────────────

    def list_agents(self, user_id: str) -> list[Agent]:
        """Return every built-in agent with the user's overrides applied."""
        return [self.get_agent(user_id, aid) for aid in BUILTIN_AGENTS]

    def get_agent(self, user_id: str, agent_id: str) -> Agent:
        """Resolve a single agent for this user.

        Raises ``KeyError`` when ``agent_id`` is not a built-in.

        Returns a fresh Agent whose mutable list/dict fields are new
        copies — callers mutating them can't corrupt BUILTIN_AGENTS or
        the in-process override cache.
        """
        base = BUILTIN_AGENTS[agent_id]
        override = self._load_overrides(user_id).get(agent_id) or {}
        return replace(base, **copy.deepcopy({
            "preset_questions": base.preset_questions,
            "enabled_legacy_tools": base.enabled_legacy_tools,
            "enabled_builtin_tools": base.enabled_builtin_tools,
            "enabled_mcp_servers": base.enabled_mcp_servers,
            "enabled_skills": base.enabled_skills,
            "parameters": base.parameters,
            **override,
        }))

    def set_override(self, user_id: str, agent_id: str, patch: Dict[str, Any]) -> Agent:
        """Merge ``patch`` into the user's override for ``agent_id``.

        Only keys in :data:`OVERRIDABLE_FIELDS` are accepted; unknown keys
        are silently dropped after a warning. Returns the resolved agent.
        """
        if agent_id not in BUILTIN_AGENTS:
            raise KeyError(agent_id)
        filtered = {k: v for k, v in patch.items() if k in OVERRIDABLE_FIELDS}
        for k in patch.keys() - filtered.keys():
            logger.warning(f"[ChatAgents] dropping non-overridable field: {k}")

        overrides = dict(self._load_overrides(user_id))
        prev = overrides.get(agent_id, {})
        overrides[agent_id] = {**prev, **filtered}
        self._save_overrides(user_id, overrides)
        return self.get_agent(user_id, agent_id)

    def reset(self, user_id: str, agent_id: str) -> Agent:
        """Drop the user's override for ``agent_id`` → revert to built-in."""
        if agent_id not in BUILTIN_AGENTS:
            raise KeyError(agent_id)
        overrides = dict(self._load_overrides(user_id))
        if overrides.pop(agent_id, None) is not None:
            self._save_overrides(user_id, overrides)
        return BUILTIN_AGENTS[agent_id]

    def invalidate(self, user_id: str) -> None:
        """Drop the in-process cache for a user (e.g. after out-of-band edit)."""
        self._cache.pop(user_id, None)


# ── DynamoDB type shims ─────────────────────────────────────────────────

def _to_ddb(obj: Any) -> Any:
    """Convert float → Decimal recursively so DynamoDB accepts it."""
    if isinstance(obj, float):
        return Decimal(str(obj))
    if isinstance(obj, dict):
        return {k: _to_ddb(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_ddb(x) for x in obj]
    return obj


def _from_ddb(obj: Any) -> Any:
    """Inverse of ``_to_ddb`` — Decimal → int/float at read time."""
    if isinstance(obj, Decimal):
        f = float(obj)
        return int(f) if f.is_integer() else f
    if isinstance(obj, dict):
        return {k: _from_ddb(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_from_ddb(x) for x in obj]
    return obj


# Module-level singleton, matches the style of model_manager / module_config.
chat_agent_registry = ChatAgentRegistry()
