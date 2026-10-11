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
from typing import Any, AsyncIterator, Dict, List, Optional

from ag_ui.core import (
    RunAgentInput,
    RunStartedEvent, RunFinishedEvent, RunErrorEvent,
    ToolCallStartEvent, ToolCallArgsEvent, ToolCallEndEvent, ToolCallResultEvent,
    CustomEvent,
)
from ag_ui.encoder import EventEncoder
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ValidationError

from backend.api.auth import get_auth_user
from backend.api.prompts.chat import (
    Agent,
    OVERRIDABLE_FIELDS,
    WORKSPACE_INSTRUCTIONS,
)
from backend.api.reply_events import ReplyEvents
from backend.api.runs import runs
from backend.common.errors import run_error_fields
from backend.common.logger import setup_logger
from backend.common.uploads import resolve_upload, log_rejected
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


def _extract_text_and_files(content: Any, owner: Optional[str] = None) -> tuple[str, List[str]]:
    """Pull plain text + a list of uploaded file paths from an AG-UI message content.

    Accepts str, dict/list-of-dict (wire shape), or Pydantic models (typed shape).
    Attachment references are resolved against `owner`'s uploads; with no owner
    (history rendering, text only) attachments are ignored.
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
            elif (ref := _attachment_ref(part)) and owner:
                # Never trust a client-supplied path: only ids of this user's uploads.
                if path := resolve_upload(ref, owner):
                    files.append(path)
                else:
                    log_rejected(ref)
        elif isinstance(part, str):
            texts.append(part)
    return "\n".join(texts), files


_MEDIA_PART_TYPES = ("image", "audio", "video", "document")


def _attachment_ref(part: Dict[str, Any]) -> Optional[str]:
    """The upload reference a content part carries, if any.

    AG-UI 1.x sends attachments as image/audio/video/document parts whose `source.value` is what the client put
    in `data` (here: the server-issued upload path); the client library converts the app's `binary` parts to that
    shape before sending. A `binary` part is still read for old clients and stored history.
    """
    if part.get("type") == "binary":
        return part.get("data") or None
    if part.get("type") in _MEDIA_PART_TYPES and isinstance(part.get("source"), dict):
        return part["source"].get("value") or None
    return None


def _upgrade_legacy_parts(raw: Any) -> Any:
    """Turn `binary` content parts into the AG-UI 1.x media parts the request model accepts.

    The AG-UI client library does this itself, but a page loaded before the 1.x upgrade (or any older client)
    still sends `binary`, and the request then failed validation with a 422 shown to the user. Same mapping as
    the library: the MIME type picks the part type, `data` becomes a data source and `url` a url source.
    """
    if not isinstance(raw, dict) or not isinstance(raw.get("messages"), list):
        return raw
    for message in raw["messages"]:
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, list):
            continue
        for i, part in enumerate(content):
            if not (isinstance(part, dict) and part.get("type") == "binary"):
                continue
            mime = part.get("mimeType") or "application/octet-stream"
            kind = next((k for k in ("image", "audio", "video") if mime.startswith(k + "/")), "document")
            if part.get("data"):
                source = {"type": "data", "value": part["data"], "mimeType": mime}
            elif part.get("url"):
                source = {"type": "url", "value": part["url"], "mimeType": mime}
            else:
                continue
            upgraded = {"type": kind, "source": source}
            if part.get("filename"):
                upgraded["metadata"] = {"filename": part["filename"]}
            content[i] = upgraded
    return raw


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


@router.get("/agents/models")
async def list_agent_models(sub: str = Depends(get_auth_user)):
    """Models eligible for chat agents (tool-using, enabled). Same filter as fallback."""
    from backend.genai.models.model_manager import model_manager
    from backend.core.module_config import module_config
    models = model_manager.get_models(filter=module_config.get_model_filter('chat')) or []
    return {"models": [
        {"model_id": m.model_id, "name": f"{m.name}, {m.api_provider}",
         "reasoning": bool(m.capabilities.reasoning)}
        for m in models
    ]}


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


def _invalidate_agent_provider(sub: str, agent_id: str) -> None:
    """Drop any cached Strands AgentProvider for this user+agent so the next
    message picks up fresh tools/skills/params. No-op for ChatService agents.
    """
    try:
        _get_agent_service().invalidate_provider_for(sub, _session_module(agent_id))
    except Exception as e:
        logger.warning(f"[chat] provider invalidation failed for {agent_id}: {e}")


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
    _invalidate_agent_provider(sub, agent_id)
    return _agent_dto(agent)


@router.post("/agents/{agent_id}/reset")
async def reset_agent(agent_id: str, sub: str = Depends(get_auth_user)):
    try:
        agent = chat_agent_registry.reset(sub, agent_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Unknown agent: {agent_id}")
    _invalidate_agent_provider(sub, agent_id)
    return _agent_dto(agent)


@router.get("/skills")
async def list_skills(sub: str = Depends(get_auth_user)):
    return {
        "skills": [
            {"name": e.name, "description": e.description}
            for e in skill_registry.list_entries()
        ],
    }


@router.get("/tools")
async def list_tools(sub: str = Depends(get_auth_user)):
    """Available legacy + Strands builtin tools for the Agents settings UI."""
    from backend.genai.tools.legacy.tool_registry import legacy_tool_registry
    from backend.genai.tools.strands.builtin_tools import BUILTIN_TOOLS

    def _legacy_desc(name: str) -> str:
        spec = legacy_tool_registry.tool_specs.get(name) or {}
        return (spec.get("toolSpec") or {}).get("description") or ""

    return {
        "legacy": [
            {"name": n, "description": _legacy_desc(n)}
            for n in sorted(legacy_tool_registry.tools.keys())
        ],
        "builtin": [
            {"name": n, "description": ""}
            for n in BUILTIN_TOOLS
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
    # Workspace files are mutable (agents can overwrite). Force the browser
    # to revalidate every time so the viewer never serves stale content.
    return FileResponse(
        path, filename=filename,
        headers={"Cache-Control": "no-cache"},
    )


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
    request: Request,
    sub: str = Depends(get_auth_user),
):
    """AG-UI SSE streaming endpoint — dispatches to ChatService or AgentService
    depending on whether the selected agent has any tools/skills enabled.

    Expects ``forwarded_props.agent_id`` — the AG-UI client's HttpAgent is
    configured with ``forwardedProps: { agent_id }`` so the field rides
    along on every runAgent call.
    """
    try:
        body = RunAgentInput.model_validate(_upgrade_legacy_parts(await request.json()))
    except ValidationError as e:
        raise RequestValidationError(e.errors()) from e
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
    msg_text, files = _extract_text_and_files(last_user_msg.content, owner=sub)
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



_SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"}


def _run_error_event(message: str) -> str:
    return _enc.encode(RunErrorEvent(message=message))


def _run_response(sub: str, agent_id: str, run_id: str, source: AsyncIterator[str]) -> StreamingResponse:
    """Start the reply as a run of its own and stream it to this client.

    The run does not depend on this connection (see backend/api/runs.py): if the client goes away the reply
    still completes, and the client can fetch it again from /stream/resume.
    """
    run = runs.start((sub, agent_id), run_id, source, _run_error_event)
    return StreamingResponse(run.follow(0), media_type="text/event-stream", headers=_SSE_HEADERS)


@router.get("/stream/resume")
async def resume_stream(
    agent_id: str = Query(...),
    run_id: str = Query(...),
    sub: str = Depends(get_auth_user),
):
    """Attach to a reply that is still running, or finished recently: all its events from the start."""
    run = runs.get((sub, agent_id), run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found (it may have expired)")
    return StreamingResponse(run.follow(0), media_type="text/event-stream", headers=_SSE_HEADERS)


@router.post("/stream/cancel")
async def cancel_stream(
    agent_id: str = Query(...),
    run_id: str = Query(...),
    sub: str = Depends(get_auth_user),
):
    """The user pressed Stop. A closed connection no longer stops a reply, so this does."""
    return {"ok": runs.cancel((sub, agent_id), run_id)}


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

            # Prepare workspace + system prompt.
            # Every agent gets a workspace dir; the user decides whether to
            # actually use it by toggling file tools in the Agents settings.
            # ContextVar set without reset: each request runs in its own task,
            # so the ContextVar is naturally scoped and cleaned up when the task
            # ends. Token-based reset would crash on cancellation because the
            # async generator may resume the finally block in a different
            # Context than the one that produced the Token.
            if agent.workspace_enabled:
                workspace_dir = workspace.ensure(workspace_user, agent.id)
                prompt_template = agent.prompt
                if "{workspace_dir}" not in prompt_template:
                    prompt_template = prompt_template + "\n\n" + WORKSPACE_INSTRUCTIONS
                system_prompt = prompt_template.format(workspace_dir=workspace_dir)
                current_workspace_dir.set(workspace_dir)
            else:
                system_prompt = agent.prompt
            current_agent_id.set(agent.id)

            tool_config = _build_tool_config(agent)
            skills = skill_registry.get_many(agent.enabled_skills)

            reply = ReplyEvents(message_id, thinking_id)
            tool_started_ids: set = set()

            async for chunk in service.streaming_reply_with_history(
                session=session,
                message=msg_text,
                system_prompt=system_prompt,
                history=history,
                tool_config=tool_config,
                persist=cloud_sync,
                files=files,
                skills=skills,
                parameters=agent.parameters,
            ):
                if not isinstance(chunk, dict):
                    continue

                if thinking := chunk.get("thinking"):
                    for event in reply.reasoning(thinking):
                        yield event

                if text := chunk.get("text"):
                    for event in reply.text(text):
                        yield event

                # Hold the AG-UI 4-event tool sequence until the terminal
                # chunk (avoids ghost entries when the LLM abandons a
                # tool_use mid-stream). But on the *first* running chunk
                # for an id, surface a one-line reasoning hint so the UI
                # shows progress while a long file_write streams its args.
                if tool_use := chunk.get("tool_use"):
                    tool_name = tool_use.get("name", "unknown")
                    tool_status = tool_use.get("status", "running")
                    tc_id = tool_use.get("tool_use_id") or f"tc-{uuid.uuid4().hex[:8]}"
                    if tool_status == "running":
                        if tc_id not in tool_started_ids:
                            tool_started_ids.add(tc_id)
                            for event in reply.reasoning(f"\n🔧 Calling {tool_name}…\n"):
                                yield event
                        continue

                    ok = tool_status in ("completed", "success")
                    mark = "✅ Done" if ok else "⚠️ Failed"
                    for event in reply.reasoning(f"\n🔧 {tool_name} {mark}\n"):
                        yield event
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

            for event in reply.finish():
                yield event
            yield _enc.encode(RunFinishedEvent(thread_id=thread_id, run_id=run_id))

        except Exception as e:
            logger.error(f"Stream error for {sub} agent={agent.id}: {e}", exc_info=True)
            yield _enc.encode(RunErrorEvent(**run_error_fields(e, "An error occurred during streaming.")))

    return _run_response(sub, agent.id, run_id, event_stream())


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

            reply = ReplyEvents(message_id, thinking_id)

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
                    for event in reply.reasoning(thinking):
                        yield event

                if text := chunk.get("text"):
                    for event in reply.text(text):
                        yield event

            for event in reply.finish():
                yield event
            yield _enc.encode(RunFinishedEvent(thread_id=thread_id, run_id=run_id))

        except Exception as e:
            logger.error(f"Stream error for {sub} agent={agent.id}: {e}", exc_info=True)
            yield _enc.encode(RunErrorEvent(**run_error_fields(e, "An error occurred during streaming.")))

    return _run_response(sub, agent.id, run_id, event_stream())
