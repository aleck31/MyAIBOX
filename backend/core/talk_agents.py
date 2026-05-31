# Copyright iX.
# SPDX-License-Identifier: MIT-0
"""Talk-with-Agent voice persona registry — the voice sibling of chat_agents.

Built-in voice personas live in :mod:`backend.api.prompts.talk`; users tweak the
mutable fields (``default_model``, ``voice_id``, ``enabled_tools``) per-agent.
Overrides persist in DynamoDB under a per-user partition and merge on top of the
built-in at read time — same mechanism as the chat agent registry, separate
``setting_name`` so the two don't collide.
"""
from __future__ import annotations

import copy
from dataclasses import replace
from decimal import Decimal
from typing import Any, Dict, List

from backend.api.prompts.talk import TalkAgent, BUILTIN_TALK_AGENTS, OVERRIDABLE_FIELDS
from backend.common.logger import logger
from backend.core.config import env_config
from backend.utils.aws import get_aws_session


DDB_SETTING_NAME = "talk_agent_overrides"


class TalkAgentRegistry:
    """Resolves built-in voice agents with per-user overrides merged in."""

    def __init__(self):
        session = get_aws_session(region_name=env_config.aws_region)
        dynamodb = session.resource("dynamodb")
        table_method = getattr(dynamodb, "Table")
        self.table = table_method(env_config.database_config["setting_table"])
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
            logger.error(f"[TalkAgents] load failed for {user_id}: {e}", exc_info=True)
            return {}
        raw = (resp.get("Item") or {}).get("overrides", {})
        overrides = _from_ddb(raw) if raw else {}
        self._cache[user_id] = overrides
        return overrides

    def _save_overrides(self, user_id: str, overrides: Dict[str, Dict]) -> None:
        self.table.put_item(Item={**self._ddb_key(user_id), "overrides": _to_ddb(overrides)})
        self._cache[user_id] = overrides

    # ── Public API ──────────────────────────────────────────────────────

    def list_agents(self, user_id: str) -> List[TalkAgent]:
        agents = [self.get_agent(user_id, aid) for aid in BUILTIN_TALK_AGENTS]
        return sorted(agents, key=lambda a: (a.order, a.id))

    def get_agent(self, user_id: str, agent_id: str) -> TalkAgent:
        """Resolve one agent for this user; raises KeyError if not built-in.

        Mutable list fields are fresh copies so callers can't corrupt the
        built-in definitions or the override cache.
        """
        base = BUILTIN_TALK_AGENTS[agent_id]
        override = self._load_overrides(user_id).get(agent_id) or {}
        return replace(base, **copy.deepcopy({
            "enabled_tools": base.enabled_tools,
            **override,
        }))

    def set_override(self, user_id: str, agent_id: str, patch: Dict[str, Any]) -> TalkAgent:
        """Merge ``patch`` (only OVERRIDABLE_FIELDS) into the user's override."""
        if agent_id not in BUILTIN_TALK_AGENTS:
            raise KeyError(agent_id)
        filtered = {k: v for k, v in patch.items() if k in OVERRIDABLE_FIELDS}
        for k in patch.keys() - filtered.keys():
            logger.warning(f"[TalkAgents] dropping non-overridable field: {k}")
        overrides = dict(self._load_overrides(user_id))
        overrides[agent_id] = {**overrides.get(agent_id, {}), **filtered}
        self._save_overrides(user_id, overrides)
        return self.get_agent(user_id, agent_id)

    def reset(self, user_id: str, agent_id: str) -> TalkAgent:
        """Drop the user's override for ``agent_id`` → revert to built-in."""
        if agent_id not in BUILTIN_TALK_AGENTS:
            raise KeyError(agent_id)
        overrides = dict(self._load_overrides(user_id))
        if overrides.pop(agent_id, None) is not None:
            self._save_overrides(user_id, overrides)
        return BUILTIN_TALK_AGENTS[agent_id]


# ── DynamoDB type shims ─────────────────────────────────────────────────

def _to_ddb(obj: Any) -> Any:
    if isinstance(obj, float):
        return Decimal(str(obj))
    if isinstance(obj, dict):
        return {k: _to_ddb(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_ddb(x) for x in obj]
    return obj


def _from_ddb(obj: Any) -> Any:
    if isinstance(obj, Decimal):
        f = float(obj)
        return int(f) if f.is_integer() else f
    if isinstance(obj, dict):
        return {k: _from_ddb(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_from_ddb(x) for x in obj]
    return obj


talk_agent_registry = TalkAgentRegistry()
