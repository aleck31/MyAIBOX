# Copyright iX.
# SPDX-License-Identifier: MIT-0
import json
import uuid
from typing import Any, List, Literal
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from ag_ui.core import (
    RunAgentInput,
    RunStartedEvent, RunFinishedEvent, RunErrorEvent,
    TextMessageStartEvent, TextMessageContentEvent, TextMessageEndEvent,
    ReasoningMessageContentEvent, ReasoningMessageEndEvent,
    ToolCallStartEvent, ToolCallArgsEvent, ToolCallEndEvent, ToolCallResultEvent,
    BaseEvent, EventType,
)
from ag_ui.encoder import EventEncoder
from core.service.service_factory import ServiceFactory
from core.module_config import module_config
from genai.models.model_manager import model_manager
from api.auth import get_auth_user
from api.prompts.assistant import ASSISTANT_PROMPT
from common.logger import setup_logger

logger = setup_logger('api.assistant')

router = APIRouter(prefix="/assistant", tags=["assistant"])

_agent_service = None
_enc = EventEncoder()

# Shim: same as persona — emit role='reasoning' for JS client compatibility
class ReasoningMessageStartEvent(BaseEvent):
    type: Literal[EventType.REASONING_MESSAGE_START] = EventType.REASONING_MESSAGE_START  # type: ignore[assignment]
    message_id: str
    role: Literal['reasoning'] = 'reasoning'


def get_agent_service():
    global _agent_service
    if _agent_service is None:
        _agent_service = ServiceFactory.create_agent_service('assistant')
    return _agent_service


class ModelUpdate(BaseModel):
    model_id: str

class CloudSyncUpdate(BaseModel):
    enabled: bool


class HistoryMessage(BaseModel):
    role: str
    content: Any


class HistorySync(BaseModel):
    messages: List[HistoryMessage] = []


@router.get("/config")
async def get_config(username: str = Depends(get_auth_user)):
    """Return available models with tool_use capability."""
    try:
        models = model_manager.get_models(filter={'tool_use': True})
        models_list = [
            {"model_id": m.model_id, "name": f"{m.name}, {m.api_provider}"}
            for m in (models or [])
        ]
        return {"models": models_list}
    except Exception as e:
        logger.error(f"Failed to get config: {e}", exc_info=True)
        return {"models": []}


@router.get("/session")
async def get_session(username: str = Depends(get_auth_user)):
    """Return current session state and chat history."""
    try:
        service = get_agent_service()
        session = await service.get_or_create_session(
            user_name=username, module_name='assistant'
        )
        model_id = await service.get_session_model(session)
        history = await service.load_session_history(session)
        cloud_sync = bool(session.context.get('cloud_sync', False))
        return {
            "session_id": session.session_id,
            "model_id": model_id,
            "cloud_sync": cloud_sync,
            "history": history,
        }
    except Exception as e:
        logger.error(f"Failed to get session: {e}", exc_info=True)
        return {"model_id": None, "cloud_sync": False, "history": []}


@router.post("/session/model")
async def update_model(body: ModelUpdate, username: str = Depends(get_auth_user)):
    try:
        service = get_agent_service()
        session = await service.get_or_create_session(
            user_name=username, module_name='assistant'
        )
        await service.update_session_model(session, body.model_id)
        return {"ok": True}
    except Exception as e:
        logger.error(f"Failed to update model: {e}", exc_info=True)
        return {"ok": False, "error": str(e)}


@router.post("/session/cloud-sync")
async def update_cloud_sync(body: CloudSyncUpdate, username: str = Depends(get_auth_user)):
    try:
        service = get_agent_service()
        session = await service.get_or_create_session(
            user_name=username, module_name='assistant'
        )
        session.context['cloud_sync'] = body.enabled
        await service.session_store.save_session(session)
        return {"ok": True, "cloud_sync": body.enabled}
    except Exception as e:
        logger.error(f"Failed to update cloud_sync: {e}", exc_info=True)
        return {"ok": False, "error": str(e)}


@router.post("/session/history")
async def sync_history(body: HistorySync, username: str = Depends(get_auth_user)):
    try:
        service = get_agent_service()
        session = await service.get_or_create_session(
            user_name=username, module_name='assistant'
        )
        session.history = [{"role": m.role, "content": m.content} for m in body.messages]
        await service.session_store.save_session(session)
        return {"ok": True, "synced": len(body.messages)}
    except Exception as e:
        logger.error(f"Failed to sync history: {e}", exc_info=True)
        return {"ok": False, "error": str(e)}


@router.delete("/session/history")
async def clear_history(username: str = Depends(get_auth_user)):
    try:
        service = get_agent_service()
        session = await service.get_or_create_session(
            user_name=username, module_name='assistant'
        )
        await service.clear_history(session)
        return {"ok": True}
    except Exception as e:
        logger.error(f"Failed to clear history: {e}", exc_info=True)
        return {"ok": False, "error": str(e)}


@router.post("/chat")
async def chat(body: RunAgentInput, username: str = Depends(get_auth_user)):
    """AG-UI SSE streaming endpoint for Assistant with tool use."""
    run_id = body.run_id or str(uuid.uuid4())
    message_id = str(uuid.uuid4())
    thinking_id = str(uuid.uuid4())

    user_messages = [m for m in body.messages if m.role == 'user']
    if not user_messages:
        async def empty():
            yield _enc.encode(RunErrorEvent(message="No user message in request."))
        return StreamingResponse(empty(), media_type="text/event-stream")

    last_user_msg = user_messages[-1]

    # Extract text and files from content
    files = []
    msg_text = last_user_msg.content if isinstance(last_user_msg.content, str) else ""
    if isinstance(last_user_msg.content, list):
        text_parts = []
        for part in last_user_msg.content:
            if isinstance(part, dict):
                if part.get("type") == "text":
                    text_parts.append(part["text"])
                elif part.get("type") == "binary" and (path := part.get("data")):
                    files.append(path)
            elif isinstance(part, str):
                text_parts.append(part)
            else:
                ptype = getattr(part, 'type', None)
                if ptype == 'text':
                    text_parts.append(getattr(part, 'text', ''))
                elif ptype == 'binary' and (path := getattr(part, 'data', None)):
                    files.append(path)
        msg_text = "\n".join(text_parts)

    # Build history (exclude last user msg and reasoning messages)
    def _normalize_content(content):
        if isinstance(content, str):
            return content
        # Pydantic model — convert to dict first
        if hasattr(content, 'model_dump'):
            content = content.model_dump()
        # Dict with text field
        if isinstance(content, dict):
            return content.get('text', '')
        if isinstance(content, list):
            texts = []
            for part in content:
                if hasattr(part, 'model_dump'):
                    part = part.model_dump()
                if isinstance(part, dict):
                    if part.get("type") == "text":
                        texts.append(part.get("text", ""))
                elif isinstance(part, str):
                    texts.append(part)
            return "\n".join(texts) if texts else ""
        return ""

    history = [
        {"role": m.role, "content": _normalize_content(m.content)}
        for m in body.messages
        if m.id != last_user_msg.id and m.role in ("user", "assistant")
    ]

    async def event_stream():
        try:
            service = get_agent_service()
            session = await service.get_or_create_session(
                user_name=username, module_name='assistant'
            )

            # Load tool config
            module_cfg = module_config.get_module_config('assistant')
            enabled_legacy_tools = module_cfg.get('enabled_tools', []) if module_cfg else []
            tool_config = {
                'enabled': True,
                'legacy_tools': enabled_legacy_tools,
                'mcp_tools_enabled': True,
                'strands_tools_enabled': True,
            }

            thread_id = body.thread_id or session.session_id
            cloud_sync = bool(session.context.get('cloud_sync', False))
            yield _enc.encode(RunStartedEvent(thread_id=thread_id, run_id=run_id))

            thinking_started = False
            text_started = False
            active_tool_calls = set()  # Track tool calls already started

            async for chunk in service.streaming_reply_with_history(
                session=session,
                message=msg_text,
                system_prompt=ASSISTANT_PROMPT,
                history=history,
                tool_config=tool_config,
                persist=cloud_sync,
                files=files,
            ):
                if not isinstance(chunk, dict):
                    continue

                if thinking := chunk.get('thinking'):
                    if not thinking_started:
                        yield _enc.encode(ReasoningMessageStartEvent(message_id=thinking_id))
                        thinking_started = True
                    yield _enc.encode(ReasoningMessageContentEvent(
                        message_id=thinking_id, delta=thinking
                    ))

                if text := chunk.get('text'):
                    if not text_started:
                        if thinking_started:
                            yield _enc.encode(ReasoningMessageEndEvent(message_id=thinking_id))
                            thinking_started = False
                        yield _enc.encode(TextMessageStartEvent(
                            message_id=message_id, role='assistant'
                        ))
                        text_started = True
                    yield _enc.encode(TextMessageContentEvent(
                        message_id=message_id, delta=text
                    ))

                # Tool use events — emit as reasoning (CoT) + structured tool call events
                if tool_use := chunk.get('tool_use'):
                    tool_name = tool_use.get('name', 'unknown')
                    tool_status = tool_use.get('status', 'running')
                    tc_id = tool_use.get('tool_use_id') or f"tc-{uuid.uuid4().hex[:8]}"
                    if not thinking_started and not text_started:
                        yield _enc.encode(ReasoningMessageStartEvent(message_id=thinking_id))
                        thinking_started = True
                    if thinking_started:
                        if tool_status == 'running' and tc_id not in active_tool_calls:
                            yield _enc.encode(ReasoningMessageContentEvent(
                                message_id=thinking_id, delta=f"\n🔧 Calling: {tool_name}\n"
                            ))
                            active_tool_calls.add(tc_id)
                            yield _enc.encode(ToolCallStartEvent(
                                tool_call_id=tc_id, tool_call_name=tool_name,
                                parent_message_id=message_id,
                            ))
                            yield _enc.encode(ToolCallArgsEvent(
                                tool_call_id=tc_id,
                                delta=json.dumps(tool_use.get('params', {})),
                            ))
                        elif tool_status in ('completed', 'success'):
                            yield _enc.encode(ReasoningMessageContentEvent(
                                message_id=thinking_id, delta=f"✅ {tool_name} done\n"
                            ))
                            if tc_id in active_tool_calls:
                                active_tool_calls.discard(tc_id)
                                yield _enc.encode(ToolCallEndEvent(tool_call_id=tc_id))
                                # Send tool result for Generative UI rendering
                                result_str = tool_use.get('result', '')
                                if result_str:
                                    yield _enc.encode(ToolCallResultEvent(
                                        tool_call_id=tc_id,
                                        message_id=message_id,
                                        content=result_str if isinstance(result_str, str) else json.dumps(result_str),
                                        role='tool',
                                    ))

            if thinking_started and not text_started:
                yield _enc.encode(ReasoningMessageEndEvent(message_id=thinking_id))
            if text_started:
                yield _enc.encode(TextMessageEndEvent(message_id=message_id))

            yield _enc.encode(RunFinishedEvent(thread_id=thread_id, run_id=run_id))

        except Exception as e:
            logger.error(f"Stream error for {username}: {e}", exc_info=True)
            yield _enc.encode(RunErrorEvent(message="An error occurred during streaming."))

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )
