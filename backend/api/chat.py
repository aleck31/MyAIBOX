"""Chat with agent module — unified endpoint for every agent.

This file replaces the old ``api/assistant.py`` + ``api/persona.py`` handlers.
Every per-user session, streaming reply, and workspace operation is keyed by
the requested ``agent_id`` (one of :data:`BUILTIN_AGENTS`).

Dispatch rules at stream time:
  - Agent has no tools (no legacy / builtin / mcp / skills)     → ChatService
  - Anything enabled                                             → AgentService
    with Strands plugins for skills and an AgentSkills injection
"""
from __future__ import annotations

import json
import os
import uuid
from typing import Any, Dict, List, Literal, Optional

from ag_ui.core import (
    RunAgentInput,
    RunStartedEvent, RunFinishedEvent, RunErrorEvent,
    TextMessageStartEvent, TextMessageContentEvent, TextMessageEndEvent,
    ReasoningMessageContentEvent, ReasoningMessageEndEvent,
    ToolCallStartEvent, ToolCallArgsEvent, ToolCallEndEvent, ToolCallResultEvent,
    CustomEvent,
    BaseEvent, EventType,
)
from ag_ui.encoder import EventEncoder
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from backend.api.auth import get_auth_user
from backend.api.prompts.chat import Agent, BUILTIN_AGENTS, OVERRIDABLE_FIELDS
from backend.common.logger import setup_logger
from backend.core import workspace
from backend.core.agent_context import current_workspace_dir, current_agent_id
from backend.core.chat_agents import chat_agent_registry
from backend.core.service.service_factory import ServiceFactory
from backend.core.skills import skill_registry


logger = setup_logger("api.chat")

router = APIRouter(prefix="/chat", tags=["chat"])

_enc = EventEncoder()

# Service singletons — one per backend type. AgentService/ChatService are
# both internally keyed by session_id, so we don't need a per-agent instance.
_agent_service = None
_chat_service = None


def _get_agent_service():
    global _agent_service
    if _agent_service is None:
        _agent_service = ServiceFactory.create_agent_service("chat")
    return _agent_service


def _get_chat_service():
    global _chat_service
    if _chat_service is None:
        _chat_service = ServiceFactory.create_chat_service("chat")
    return _chat_service


# Same shim the old handlers used — keeps AG-UI JS client happy with role='reasoning'.
class ReasoningMessageStartEvent(BaseEvent):
    type: Literal[EventType.REASONING_MESSAGE_START] = EventType.REASONING_MESSAGE_START  # type: ignore[assignment]
    message_id: str
    role: Literal["reasoning"] = "reasoning"


# ─── Utilities ───────────────────────────────────────────────────────────────

def _resolve_agent(sub: str, agent_id: str) -> Agent:
    """Look up a built-in agent with the user's overrides applied, 404 on miss."""
    try:
        return chat_agent_registry.get_agent(sub, agent_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Unknown agent: {agent_id}")


def _workspace_user(request: Request, sub: str) -> str:
    """Prefer the human-readable Cognito username for filesystem paths; fall back to sub."""
    user = getattr(request.state, "user", None) or {}
    return user.get("username") or sub


def _uses_agent_service(agent: Agent) -> bool:
    """Any tool / skill enabled → go through Strands agent loop."""
    return bool(
        agent.enabled_legacy_tools
        or agent.enabled_builtin_tools
        or agent.enabled_mcp_servers
        or agent.enabled_skills
    )


def _build_tool_config(agent: Agent) -> Dict[str, Any]:
    """Translate agent config into the shape ``ToolProvider`` consumes."""
    return {
        "enabled": True,
        "legacy_tools": list(agent.enabled_legacy_tools),
        "builtin_tools": list(agent.enabled_builtin_tools),
        "mcp_servers": list(agent.enabled_mcp_servers),
    }


def _agent_dto(agent: Agent) -> Dict[str, Any]:
    """Wire format for Agent objects."""
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


def _extract_text_and_files(content: Any) -> tuple[str, List[str]]:
    """Pull plain text + a list of uploaded file paths from an AG-UI message content.

    Accepts str, dict/list-of-dict (wire shape), or Pydantic models (typed shape).
    """
    if isinstance(content, str):
        return content, []
    if not isinstance(content, list):
        return "", []
    texts: List[str] = []
    files: List[str] = []
    for part in content:
        if hasattr(part, "model_dump"):
            part = part.model_dump()
        if isinstance(part, dict):
            if part.get("type") == "text":
                texts.append(part.get("text", ""))
            elif part.get("type") == "binary":
                if p := part.get("data"):
                    files.append(p)
        elif isinstance(part, str):
            texts.append(part)
    return "\n".join(texts), files


def _normalize_history_content(content: Any) -> str:
    """Reduce a history message's content to plain text for Strands / ChatService."""
    if isinstance(content, str):
        return content
    if hasattr(content, "model_dump"):
        content = content.model_dump()
    if isinstance(content, dict):
        return content.get("text", "")
    if isinstance(content, list):
        text, _ = _extract_text_and_files(content)
        return text
    return ""


# ─── Agent registry endpoints (from PR 2a) ──────────────────────────────────

@router.get("/agents")
async def list_agents(sub: str = Depends(get_auth_user)):
    return {"agents": [_agent_dto(a) for a in chat_agent_registry.list_agents(sub)]}


@router.get("/agents/{agent_id}")
async def get_agent(agent_id: str, sub: str = Depends(get_auth_user)):
    return _agent_dto(_resolve_agent(sub, agent_id))


class AgentPatchBody(BaseModel):
    default_model: Optional[str] = None
    enabled_legacy_tools: Optional[List[str]] = None
    enabled_builtin_tools: Optional[List[str]] = None
    enabled_mcp_servers: Optional[List[str]] = None
    enabled_skills: Optional[List[str]] = None
    parameters: Optional[Dict[str, Any]] = None


@router.patch("/agents/{agent_id}")
async def patch_agent(agent_id: str, body: AgentPatchBody, sub: str = Depends(get_auth_user)):
    patch = {k: v for k, v in body.model_dump().items() if v is not None}
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
    try:
        agent = chat_agent_registry.reset(sub, agent_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Unknown agent: {agent_id}")
    return _agent_dto(agent)


@router.get("/skills")
async def list_skills(sub: str = Depends(get_auth_user)):
    return {
        "skills": [
            {"name": e.name, "description": e.description}
            for e in skill_registry.list_entries()
        ],
    }


# ─── Per-agent session state ────────────────────────────────────────────────
# Session keys are ``{sub}_{agent_id}`` — each agent gets its own thread of
# history, model selection, and cloud-sync flag.


def _session_module(agent_id: str) -> str:
    """Session module name for the given agent.

    Format: ``chat.<agent_id>`` — the ``chat.`` prefix groups all Chat-module
    sessions so future queries can ``begins_with("chat.")`` to fetch the
    whole module; the suffix keeps per-agent isolation (each agent gets its
    own session thread).
    """
    return f"chat.{agent_id}"


@router.get("/session")
async def get_session(agent_id: str = Query(...), sub: str = Depends(get_auth_user)):
    """Return thread id, chosen model, cloud-sync flag, and persisted history."""
    agent = _resolve_agent(sub, agent_id)
    try:
        if _uses_agent_service(agent):
            service = _get_agent_service()
            session = await service.get_or_create_session(
                user_name=sub, module_name=_session_module(agent_id),
            )
            model_id = await service.get_session_model(session)
            history = await service.load_session_history(session)
        else:
            service = _get_chat_service()
            session = await service.get_or_create_session(
                user_name=sub, module_name=_session_module(agent_id),
            )
            model_id = await service.get_session_model(session)
            history = await service.load_session_history(session)
        cloud_sync = bool(session.context.get("cloud_sync", False))
        return {
            "session_id": session.session_id,
            "model_id": model_id or agent.default_model,
            "cloud_sync": cloud_sync,
            "history": history,
        }
    except Exception as e:
        logger.error(f"Failed to get session for {agent_id}: {e}", exc_info=True)
        return {"model_id": None, "cloud_sync": False, "history": []}


class ModelUpdate(BaseModel):
    model_id: str


@router.post("/session/model")
async def update_model(
    body: ModelUpdate,
    agent_id: str = Query(...),
    sub: str = Depends(get_auth_user),
):
    agent = _resolve_agent(sub, agent_id)
    try:
        service = _get_agent_service() if _uses_agent_service(agent) else _get_chat_service()
        session = await service.get_or_create_session(
            user_name=sub, module_name=_session_module(agent_id),
        )
        await service.update_session_model(session, body.model_id)
        return {"ok": True}
    except Exception as e:
        logger.error(f"Failed to update model for {agent_id}: {e}", exc_info=True)
        return {"ok": False, "error": str(e)}


class CloudSyncUpdate(BaseModel):
    enabled: bool


@router.post("/session/cloud-sync")
async def update_cloud_sync(
    body: CloudSyncUpdate,
    agent_id: str = Query(...),
    sub: str = Depends(get_auth_user),
):
    agent = _resolve_agent(sub, agent_id)
    try:
        service = _get_agent_service() if _uses_agent_service(agent) else _get_chat_service()
        session = await service.get_or_create_session(
            user_name=sub, module_name=_session_module(agent_id),
        )
        session.context["cloud_sync"] = body.enabled
        await service.session_store.save_session(session)
        return {"ok": True, "cloud_sync": body.enabled}
    except Exception as e:
        logger.error(f"Failed to update cloud_sync for {agent_id}: {e}", exc_info=True)
        return {"ok": False, "error": str(e)}


class HistoryMessage(BaseModel):
    role: str
    content: Any


class HistorySync(BaseModel):
    messages: List[HistoryMessage] = []


@router.post("/session/history")
async def sync_history(
    body: HistorySync,
    agent_id: str = Query(...),
    sub: str = Depends(get_auth_user),
):
    agent = _resolve_agent(sub, agent_id)
    try:
        service = _get_agent_service() if _uses_agent_service(agent) else _get_chat_service()
        session = await service.get_or_create_session(
            user_name=sub, module_name=_session_module(agent_id),
        )
        session.history = [{"role": m.role, "content": m.content} for m in body.messages]
        await service.session_store.save_session(session)
        return {"ok": True, "synced": len(body.messages)}
    except Exception as e:
        logger.error(f"Failed to sync history for {agent_id}: {e}", exc_info=True)
        return {"ok": False, "error": str(e)}


@router.delete("/session/history")
async def clear_history(agent_id: str = Query(...), sub: str = Depends(get_auth_user)):
    agent = _resolve_agent(sub, agent_id)
    try:
        service = _get_agent_service() if _uses_agent_service(agent) else _get_chat_service()
        session = await service.get_or_create_session(
            user_name=sub, module_name=_session_module(agent_id),
        )
        await service.clear_history(session)
        return {"ok": True}
    except Exception as e:
        logger.error(f"Failed to clear history for {agent_id}: {e}", exc_info=True)
        return {"ok": False, "error": str(e)}


# ─── Workspace ──────────────────────────────────────────────────────────────
# Per-user, per-agent. Only agents with ``workspace_enabled=True`` are expected
# to write files; other agents will just return empty lists.


@router.get("/workspace")
async def list_workspace(
    request: Request,
    agent_id: str = Query(...),
    sub: str = Depends(get_auth_user),
):
    _resolve_agent(sub, agent_id)  # 404 guard
    user = _workspace_user(request, sub)
    try:
        files = workspace.list_files(user, agent_id)
        return {
            "files": [
                {"name": f.name, "size": f.size, "mtime": f.mtime}
                for f in files
            ],
        }
    except Exception as e:
        logger.error(f"Failed to list workspace {agent_id} for {user}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to list workspace")


@router.get("/workspace/{filename}")
async def get_workspace_file(
    filename: str,
    request: Request,
    agent_id: str = Query(...),
    sub: str = Depends(get_auth_user),
):
    _resolve_agent(sub, agent_id)
    user = _workspace_user(request, sub)
    try:
        ws_dir = workspace.path_for(user, agent_id)
        path = workspace.safe_join(ws_dir, filename)
    except workspace.WorkspaceError:
        raise HTTPException(status_code=400, detail="Invalid filename")
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(path, filename=filename)


@router.delete("/workspace/{filename}")
async def delete_workspace_file(
    filename: str,
    agent_id: str = Query(...),
    sub: str = Depends(get_auth_user),
    request: Request = None,  # type: ignore[assignment]
):
    _resolve_agent(sub, agent_id)
    user = _workspace_user(request, sub)
    try:
        removed = workspace.delete_file(user, agent_id, filename)
    except workspace.WorkspaceError:
        raise HTTPException(status_code=400, detail="Invalid filename")
    if not removed:
        raise HTTPException(status_code=404, detail="Not found")
    return {"ok": True}


# ─── Streaming chat ─────────────────────────────────────────────────────────

@router.post("/stream")
async def chat_stream(
    body: RunAgentInput,
    request: Request,
    sub: str = Depends(get_auth_user),
):
    """AG-UI SSE streaming endpoint — dispatches to ChatService or AgentService
    depending on whether the selected agent has any tools/skills enabled.

    Expects ``forwarded_props.agent_id`` — the AG-UI client's HttpAgent is
    configured with ``forwardedProps: { agent_id }`` so the field rides
    along on every runAgent call.
    """
    forwarded = body.forwarded_props or {}
    agent_id = forwarded.get("agent_id") if isinstance(forwarded, dict) else None
    if not agent_id:
        raise HTTPException(status_code=400, detail="agent_id is required")
    agent = _resolve_agent(sub, agent_id)
    run_id = body.run_id or str(uuid.uuid4())
    message_id = str(uuid.uuid4())
    thinking_id = str(uuid.uuid4())

    user_messages = [m for m in body.messages if m.role == "user"]
    if not user_messages:
        async def empty():
            yield _enc.encode(RunErrorEvent(message="No user message in request."))
        return StreamingResponse(empty(), media_type="text/event-stream")

    last_user_msg = user_messages[-1]
    msg_text, files = _extract_text_and_files(last_user_msg.content)
    history = [
        {"role": m.role, "content": _normalize_history_content(m.content)}
        for m in body.messages
        if m.id != last_user_msg.id and m.role in ("user", "assistant")
    ]

    workspace_user = _workspace_user(request, sub)

    if _uses_agent_service(agent):
        return await _stream_agent(
            agent=agent,
            sub=sub,
            workspace_user=workspace_user,
            msg_text=msg_text,
            files=files,
            history=history,
            body=body,
            run_id=run_id,
            message_id=message_id,
            thinking_id=thinking_id,
        )
    else:
        return await _stream_chat(
            agent=agent,
            sub=sub,
            msg_text=msg_text,
            files=files,
            history=history,
            body=body,
            run_id=run_id,
            message_id=message_id,
            thinking_id=thinking_id,
        )


async def _stream_agent(
    *,
    agent: Agent,
    sub: str,
    workspace_user: str,
    msg_text: str,
    files: List[str],
    history: List[Dict],
    body: RunAgentInput,
    run_id: str,
    message_id: str,
    thinking_id: str,
):
    """AgentService path — tools + workspace + skills."""
    service = _get_agent_service()

    async def event_stream():
        try:
            session = await service.get_or_create_session(
                user_name=sub, module_name=_session_module(agent.id),
            )
            thread_id = body.thread_id or session.session_id
            cloud_sync = bool(session.context.get("cloud_sync", False))
            yield _enc.encode(RunStartedEvent(thread_id=thread_id, run_id=run_id))

            # Prepare workspace + system prompt
            if agent.workspace_enabled:
                workspace_dir = workspace.ensure(workspace_user, agent.id)
                system_prompt = agent.prompt.format(workspace_dir=workspace_dir)
                ctx_token = current_workspace_dir.set(workspace_dir)
            else:
                system_prompt = agent.prompt
                ctx_token = None
            agent_id_token = current_agent_id.set(agent.id)

            tool_config = _build_tool_config(agent)
            skills = skill_registry.get_many(agent.enabled_skills)

            thinking_started = False
            text_started = False

            try:
                async for chunk in service.streaming_reply_with_history(
                    session=session,
                    message=msg_text,
                    system_prompt=system_prompt,
                    history=history,
                    tool_config=tool_config,
                    persist=cloud_sync,
                    files=files,
                    skills=skills,
                ):
                    if not isinstance(chunk, dict):
                        continue

                    if thinking := chunk.get("thinking"):
                        if not thinking_started:
                            yield _enc.encode(ReasoningMessageStartEvent(message_id=thinking_id))
                            thinking_started = True
                        yield _enc.encode(ReasoningMessageContentEvent(
                            message_id=thinking_id, delta=thinking,
                        ))

                    if text := chunk.get("text"):
                        if not text_started:
                            if thinking_started:
                                yield _enc.encode(ReasoningMessageEndEvent(message_id=thinking_id))
                                thinking_started = False
                            yield _enc.encode(TextMessageStartEvent(
                                message_id=message_id, role="assistant",
                            ))
                            text_started = True
                        yield _enc.encode(TextMessageContentEvent(
                            message_id=message_id, delta=text,
                        ))

                    # Hold AG-UI tool sequence until the terminal chunk — abandoned
                    # mid-stream candidates never reach a terminal and stay invisible.
                    if tool_use := chunk.get("tool_use"):
                        tool_name = tool_use.get("name", "unknown")
                        tool_status = tool_use.get("status", "running")
                        tc_id = tool_use.get("tool_use_id") or f"tc-{uuid.uuid4().hex[:8]}"
                        if tool_status == "running":
                            continue

                        if not thinking_started and not text_started:
                            yield _enc.encode(ReasoningMessageStartEvent(message_id=thinking_id))
                            thinking_started = True
                        ok = tool_status in ("completed", "success")
                        mark = "✅" if ok else "⚠️"
                        yield _enc.encode(ReasoningMessageContentEvent(
                            message_id=thinking_id, delta=f"\n🔧 {tool_name} {mark}\n",
                        ))
                        yield _enc.encode(ToolCallStartEvent(
                            tool_call_id=tc_id, tool_call_name=tool_name,
                            parent_message_id=message_id,
                        ))
                        yield _enc.encode(ToolCallArgsEvent(
                            tool_call_id=tc_id,
                            delta=json.dumps(tool_use.get("params", {})),
                        ))
                        yield _enc.encode(ToolCallEndEvent(tool_call_id=tc_id))
                        if agent.workspace_enabled:
                            yield _enc.encode(CustomEvent(
                                name="workspace_updated", value={"tool": tool_name},
                            ))
                        result_str = tool_use.get("result", "")
                        if result_str:
                            yield _enc.encode(ToolCallResultEvent(
                                tool_call_id=tc_id,
                                message_id=message_id,
                                content=result_str if isinstance(result_str, str) else json.dumps(result_str),
                                role="tool",
                            ))
            finally:
                if ctx_token is not None:
                    current_workspace_dir.reset(ctx_token)
                current_agent_id.reset(agent_id_token)

            if thinking_started and not text_started:
                yield _enc.encode(ReasoningMessageEndEvent(message_id=thinking_id))
            if text_started:
                yield _enc.encode(TextMessageEndEvent(message_id=message_id))
            yield _enc.encode(RunFinishedEvent(thread_id=thread_id, run_id=run_id))

        except Exception as e:
            logger.error(f"Stream error for {sub} agent={agent.id}: {e}", exc_info=True)
            yield _enc.encode(RunErrorEvent(message="An error occurred during streaming."))

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


async def _stream_chat(
    *,
    agent: Agent,
    sub: str,
    msg_text: str,
    files: List[str],
    history: List[Dict],
    body: RunAgentInput,
    run_id: str,
    message_id: str,
    thinking_id: str,
):
    """ChatService path — plain conversation, no tools."""
    service = _get_chat_service()

    ui_input: Dict[str, Any] = {"text": msg_text}
    if files:
        ui_input["files"] = files

    async def event_stream():
        try:
            session = await service.get_or_create_session(
                user_name=sub, module_name=_session_module(agent.id),
            )
            session.context["system_prompt"] = agent.prompt
            thread_id = body.thread_id or session.session_id
            cloud_sync = await service.get_session_cloud_sync(session)

            # Parameters are keyed with the style_params names ChatService uses
            style_params = {k: v for k, v in agent.parameters.items() if v is not None}

            yield _enc.encode(RunStartedEvent(thread_id=thread_id, run_id=run_id))

            thinking_started = False
            text_started = False

            async for chunk in service.streaming_reply(
                session=session,
                message=ui_input,
                history=history,
                style_params=style_params,
                persist=cloud_sync,
            ):
                if not isinstance(chunk, dict):
                    continue

                if thinking := chunk.get("thinking"):
                    if not thinking_started:
                        yield _enc.encode(ReasoningMessageStartEvent(message_id=thinking_id))
                        thinking_started = True
                    yield _enc.encode(ReasoningMessageContentEvent(
                        message_id=thinking_id, delta=thinking,
                    ))

                if text := chunk.get("text"):
                    if not text_started:
                        if thinking_started:
                            yield _enc.encode(ReasoningMessageEndEvent(message_id=thinking_id))
                        yield _enc.encode(TextMessageStartEvent(
                            message_id=message_id, role="assistant",
                        ))
                        text_started = True
                    yield _enc.encode(TextMessageContentEvent(
                        message_id=message_id, delta=text,
                    ))

            if thinking_started and not text_started:
                yield _enc.encode(ReasoningMessageEndEvent(message_id=thinking_id))
            if text_started:
                yield _enc.encode(TextMessageEndEvent(message_id=message_id))
            yield _enc.encode(RunFinishedEvent(thread_id=thread_id, run_id=run_id))

        except Exception as e:
            logger.error(f"Stream error for {sub} agent={agent.id}: {e}", exc_info=True)
            yield _enc.encode(RunErrorEvent(message="An error occurred during streaming."))

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )
