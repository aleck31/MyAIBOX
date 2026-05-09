"""Chat module — agent registry endpoints.

This is PR 2a: read-only plus a PATCH for user overrides. The streaming
endpoint and session plumbing come in PR 2b.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.api.auth import get_auth_user
from backend.api.prompts.chat import Agent, OVERRIDABLE_FIELDS
from backend.common.logger import setup_logger
from backend.core.chat_agents import chat_agent_registry
from backend.core.skills import skill_registry


logger = setup_logger("api.chat")

router = APIRouter(prefix="/chat", tags=["chat"])


def _agent_dto(agent: Agent) -> Dict[str, Any]:
    """Shape an Agent for the wire. Keep it flat; UI mirrors these fields."""
    return {
        "id": agent.id,
        "name": agent.name,
        "description": agent.description,
        "avatar": agent.avatar,
        "default_model": agent.default_model,
        "preset_questions": list(agent.preset_questions),
        "enabled_legacy_tools": list(agent.enabled_legacy_tools),
        "enabled_builtin_tools": list(agent.enabled_builtin_tools),
        "enabled_mcp_servers": list(agent.enabled_mcp_servers),
        "enabled_skills": list(agent.enabled_skills),
        "parameters": dict(agent.parameters),
        "workspace_enabled": agent.workspace_enabled,
    }


@router.get("/agents")
async def list_agents(sub: str = Depends(get_auth_user)):
    """All agents visible to this user (built-ins with their overrides merged in)."""
    return {"agents": [_agent_dto(a) for a in chat_agent_registry.list_agents(sub)]}


@router.get("/agents/{agent_id}")
async def get_agent(agent_id: str, sub: str = Depends(get_auth_user)):
    try:
        agent = chat_agent_registry.get_agent(sub, agent_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Unknown agent: {agent_id}")
    return _agent_dto(agent)


class AgentPatchBody(BaseModel):
    default_model: Optional[str] = None
    enabled_legacy_tools: Optional[List[str]] = None
    enabled_builtin_tools: Optional[List[str]] = None
    enabled_mcp_servers: Optional[List[str]] = None
    enabled_skills: Optional[List[str]] = None
    parameters: Optional[Dict[str, Any]] = None


@router.patch("/agents/{agent_id}")
async def patch_agent(
    agent_id: str,
    body: AgentPatchBody,
    sub: str = Depends(get_auth_user),
):
    """Merge user overrides onto the built-in agent.

    Only fields present on the request body (non-``None``) are applied —
    this lets the UI send partial PATCHes without wiping other overrides.
    """
    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    # Verify every incoming field is actually overridable — defensive, the
    # pydantic model already limits the shape.
    for k in patch:
        if k not in OVERRIDABLE_FIELDS:
            raise HTTPException(status_code=400, detail=f"field not overridable: {k}")
    try:
        agent = chat_agent_registry.set_override(sub, agent_id, patch)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Unknown agent: {agent_id}")
    return _agent_dto(agent)


@router.post("/agents/{agent_id}/reset")
async def reset_agent(agent_id: str, sub: str = Depends(get_auth_user)):
    """Drop the user's override; the agent reverts to its code-owned defaults."""
    try:
        agent = chat_agent_registry.reset(sub, agent_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Unknown agent: {agent_id}")
    return _agent_dto(agent)


# ─── Skills listing (for the settings UI) ──────────────────────────────────

@router.get("/skills")
async def list_skills(sub: str = Depends(get_auth_user)):
    """Expose skill metadata the user can pick from when overriding agents."""
    return {
        "skills": [
            {"name": e.name, "description": e.description}
            for e in skill_registry.list_entries()
        ],
    }
