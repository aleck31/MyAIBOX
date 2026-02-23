# Copyright iX.
# SPDX-License-Identifier: MIT-0
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
)
from ag_ui.core import (
    BaseEvent, EventType,
)
from ag_ui.encoder import EventEncoder
from core.service.service_factory import ServiceFactory
from genai.models.model_manager import model_manager
from api.auth import get_auth_user
from webui.modules.persona.prompts import PERSONA_ROLES
from common.logger import setup_logger

logger = setup_logger('api.persona')

router = APIRouter(prefix="/persona", tags=["persona"])

# Module-level instances
_chat_service = None
_enc = EventEncoder()

# TODO: Remove this shim once ag-ui-protocol (Python) and @ag-ui/client (JS) converge.
#
# Schema mismatch between the two AG-UI package tracks:
#   ag-ui-protocol >= 0.1.8  (Python)  →  ReasoningMessageStartEvent.role = Literal['assistant']
#   @ag-ui/core    == 0.0.45 (JS/Zod)  →  ReasoningMessageStartEventSchema.role = z.literal('reasoning')
#
# The JS client rejects role='assistant' with a Zod validation error at runtime.
# Shadow the SDK class locally to emit role='reasoning' until both sides align.
class ReasoningMessageStartEvent(BaseEvent):
    type: Literal[EventType.REASONING_MESSAGE_START] = EventType.REASONING_MESSAGE_START  # type: ignore[assignment]
    message_id: str
    role: Literal['reasoning'] = 'reasoning'


def get_chat_service():
    global _chat_service
    if _chat_service is None:
        _chat_service = ServiceFactory.create_chat_service('persona')
    return _chat_service


# ─── Request models (our own API surface) ────────────────────────────────────

class RoleUpdate(BaseModel):
    persona_role: str


class ModelUpdate(BaseModel):
    model_id: str


class CloudSyncUpdate(BaseModel):
    enabled: bool


class HistoryMessage(BaseModel):
    role: str
    content: Any  # str | list[ContentPart] — preserved as-is from AG-UI


class HistorySync(BaseModel):
    messages: List[HistoryMessage] = []


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/config")
async def get_config(username: str = Depends(get_auth_user)):
    """Return available models and persona roles for UI initialization."""
    try:
        models = model_manager.get_models(filter={'output_modality': ['text']})
        models_list = [
            {"model_id": m.model_id, "name": f"{m.name}, {m.api_provider}"}
            for m in (models or [])
        ]
        roles_list = [
            {"key": k, "display_name": v["display_name"]}
            for k, v in PERSONA_ROLES.items()
        ]
        return {"models": models_list, "persona_roles": roles_list}
    except Exception as e:
        logger.error(f"Failed to get config: {e}", exc_info=True)
        return {"models": [], "persona_roles": []}


@router.get("/session")
async def get_session(username: str = Depends(get_auth_user)):
    """Return current session: model_id, persona_role, cloud_sync, and chat history."""
    try:
        service = get_chat_service()
        session = await service.get_or_create_session(
            user_name=username,
            module_name='persona'
        )
        model_id = await service.get_session_model(session)
        persona_role = await service.get_session_role(session)
        cloud_sync = await service.get_session_cloud_sync(session)
        history = await service.load_session_history(session)
        return {
            "session_id": session.session_id,
            "model_id": model_id,
            "persona_role": persona_role,
            "cloud_sync": cloud_sync,
            "history": history
        }
    except Exception as e:
        logger.error(f"Failed to get session for {username}: {e}", exc_info=True)
        return {"model_id": None, "persona_role": "default", "cloud_sync": False, "history": []}


@router.post("/session/role")
async def update_role(
    body: RoleUpdate,
    username: str = Depends(get_auth_user)
):
    """Persist persona role selection to session."""
    try:
        service = get_chat_service()
        session = await service.get_or_create_session(
            user_name=username,
            module_name='persona'
        )
        await service.update_session_role(session, body.persona_role)
        return {"ok": True, "persona_role": body.persona_role}
    except Exception as e:
        logger.error(f"Failed to update role for {username}: {e}", exc_info=True)
        return {"ok": False, "error": str(e)}


@router.post("/session/model")
async def update_model(
    body: ModelUpdate,
    username: str = Depends(get_auth_user)
):
    """Persist model selection to session."""
    try:
        service = get_chat_service()
        session = await service.get_or_create_session(
            user_name=username,
            module_name='persona'
        )
        await service.update_session_model(session, body.model_id)
        return {"ok": True, "model_id": body.model_id}
    except Exception as e:
        logger.error(f"Failed to update model for {username}: {e}", exc_info=True)
        return {"ok": False, "error": str(e)}


@router.post("/session/cloud-sync")
async def update_cloud_sync(
    body: CloudSyncUpdate,
    username: str = Depends(get_auth_user)
):
    """Persist cloud sync preference to session."""
    try:
        service = get_chat_service()
        session = await service.get_or_create_session(
            user_name=username,
            module_name='persona'
        )
        await service.update_session_cloud_sync(session, body.enabled)
        return {"ok": True, "cloud_sync": body.enabled}
    except Exception as e:
        logger.error(f"Failed to update cloud_sync for {username}: {e}", exc_info=True)
        return {"ok": False, "error": str(e)}


@router.post("/session/history")
async def sync_history(
    body: HistorySync,
    username: str = Depends(get_auth_user)
):
    """Overwrite session history with the full conversation from the client."""
    try:
        service = get_chat_service()
        session = await service.get_or_create_session(
            user_name=username,
            module_name='persona'
        )
        await service.sync_history(session, [m.model_dump() for m in body.messages])
        return {"ok": True, "synced": len(body.messages)}
    except Exception as e:
        logger.error(f"Failed to sync history for {username}: {e}", exc_info=True)
        return {"ok": False, "error": str(e)}


@router.delete("/session/history")
async def clear_history(username: str = Depends(get_auth_user)):
    """Clear chat history for the current session."""
    try:
        service = get_chat_service()
        session = await service.get_or_create_session(
            user_name=username,
            module_name='persona'
        )
        await service.clear_history(session)
        return {"ok": True}
    except Exception as e:
        logger.error(f"Failed to clear history for {username}: {e}", exc_info=True)
        return {"ok": False, "error": str(e)}


@router.post("/chat")
async def chat(
    body: RunAgentInput,
    username: str = Depends(get_auth_user)
):
    """AG-UI SSE streaming endpoint. Accepts RunAgentInput, emits AG-UI events."""
    run_id = body.run_id or str(uuid.uuid4())
    message_id = str(uuid.uuid4())
    thinking_id = str(uuid.uuid4())

    # Extract last user message from AG-UI messages list
    user_messages = [m for m in body.messages if m.role == 'user']
    if not user_messages:
        async def empty_stream():
            yield _enc.encode(RunErrorEvent(message="No user message in request."))
        return StreamingResponse(empty_stream(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache",
                                          "X-Accel-Buffering": "no"})

    last_user_msg = user_messages[-1]

    # Extract file paths from attachment content parts (if any)
    files = []
    msg_text = last_user_msg.content
    if isinstance(last_user_msg.content, list):
        text_parts = []
        for part in last_user_msg.content:
            if isinstance(part, dict):
                if part.get("type") == "text":
                    text_parts.append(part["text"])
                elif part.get("type") == "binary":
                    # data field contains the file path from upload endpoint
                    if path := part.get("data"):
                        files.append(path)
            elif isinstance(part, str):
                text_parts.append(part)
            else:
                # Pydantic model objects (TextInputContent, BinaryInputContent)
                ptype = getattr(part, 'type', None)
                if ptype == 'text':
                    text_parts.append(getattr(part, 'text', ''))
                elif ptype == 'binary':
                    if path := getattr(part, 'data', None):
                        files.append(path)
        msg_text = "\n".join(text_parts)

    ui_input = {"text": msg_text}
    if files:
        ui_input["files"] = files

    # Convert AG-UI messages to ChatService history format.
    # Exclude: the last user message (sent separately) and any role='reasoning'
    # messages — those are AG-UI chain-of-thought bubbles; LLM APIs only accept
    # role in {user, assistant} for multi-turn history.
    def _normalize_content(content):
        """Normalize AG-UI message content (str | list[Pydantic]) to str or dict."""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            texts, files = [], []
            for part in content:
                if isinstance(part, dict):
                    if part.get("type") == "text": texts.append(part["text"])
                    elif part.get("type") == "binary" and part.get("data"): files.append(part["data"])
                elif isinstance(part, str):
                    texts.append(part)
                else:
                    ptype = getattr(part, 'type', None)
                    if ptype == 'text': texts.append(getattr(part, 'text', ''))
                    elif ptype == 'binary':
                        if p := getattr(part, 'data', None): files.append(p)
            result: dict[str, Any] = {"text": "\n".join(texts)}
            if files: result["files"] = files
            return result
        return str(content)

    history = [
        {"role": m.role, "content": _normalize_content(m.content)}
        for m in body.messages
        if m.id != last_user_msg.id and m.role in ("user", "assistant")
    ]

    async def event_stream():
        try:
            service = get_chat_service()
            session = await service.get_or_create_session(
                user_name=username,
                module_name='persona'
            )

            # Apply persona role system prompt
            persona_role = await service.get_session_role(session)
            style_config = PERSONA_ROLES.get(persona_role) or PERSONA_ROLES['default']
            session.context['system_prompt'] = style_config["prompt"]
            style_params = {
                k: v for k, v in style_config["options"].items() if v is not None
            }

            thread_id = body.thread_id or session.session_id
            cloud_sync = await service.get_session_cloud_sync(session)

            yield _enc.encode(RunStartedEvent(thread_id=thread_id, run_id=run_id))

            thinking_started = False
            text_started = False

            async for chunk in service.streaming_reply(
                session=session,
                message=ui_input,
                history=history,
                style_params=style_params,
                persist=cloud_sync
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
                        yield _enc.encode(TextMessageStartEvent(
                            message_id=message_id, role='assistant'
                        ))
                        text_started = True
                    yield _enc.encode(TextMessageContentEvent(
                        message_id=message_id, delta=text
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
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        }
    )
