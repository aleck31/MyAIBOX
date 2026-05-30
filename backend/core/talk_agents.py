# Copyright iX.
# SPDX-License-Identifier: MIT-0
"""Talk-with-Agent voice persona registry — the voice sibling of chat_agents.

MVP: built-in voice agents only (no per-user overrides yet). Mirrors the chat
agent registry's read API so the frontend lists and resolves voice agents the
same way it does chat agents.
"""
from typing import List

from backend.api.prompts.talk import TalkAgent, BUILTIN_TALK_AGENTS


class TalkAgentRegistry:
    """Resolves built-in voice agents (sorted for stable sidebar order)."""

    def list_agents(self) -> List[TalkAgent]:
        return sorted(BUILTIN_TALK_AGENTS.values(), key=lambda a: (a.order, a.id))

    def get_agent(self, agent_id: str) -> TalkAgent:
        agent = BUILTIN_TALK_AGENTS.get(agent_id)
        if agent is None:
            raise KeyError(agent_id)
        return agent


talk_agent_registry = TalkAgentRegistry()
