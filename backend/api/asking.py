# Copyright iX.
# SPDX-License-Identifier: MIT-0
import uuid
from typing import List
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, Query
from fastapi.responses import StreamingResponse
from ag_ui.core import (
    RunStartedEvent, RunFinishedEvent, RunErrorEvent,
)
from ag_ui.encoder import EventEncoder
from backend.core.module_config import module_config
from backend.genai.models.model_manager import model_manager
from backend.genai.models.providers import LLMMessage, LLMParameters, create_model_provider
from backend.genai.models.thinking import DEFAULT_INTENT
from backend.api.auth import get_auth_user
from backend.api.prompts.asking import SYSTEM_PROMPT
from backend.api.reply_events import ReplyEvents
from backend.api.runs import runs
from backend.common.errors import ModelUnavailableError, run_error_fields
from backend.common.provider_cache import ProviderCache
from backend.common.async_stream import aiter_sync
from backend.common.logger import setup_logger
from backend.common.uploads import save_upload

logger = setup_logger('api.asking')

router = APIRouter(prefix="/asking", tags=["asking"])

_enc = EventEncoder()

def _run_slot(run_id: str) -> str:
    """Registry slot of one Asking answer. Asking keeps no conversation state, so answers do not replace each
    other (two tabs can ask at once); Chat uses the agent id, where a newer message does replace the older."""
    return f"module:asking:{run_id}"
_SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


def _run_error_event(message: str) -> str:
    return _enc.encode(RunErrorEvent(message=message))
_provider_cache = ProviderCache()


def _get_provider(model_id: str):
    model = model_manager.get_model_by_id(model_id)
    if not model:
        raise ModelUnavailableError(model_id)
    params = dict(module_config.get_inference_params('asking') or {})
    tools = module_config.get_enabled_tools('asking') or []
    # Thinking intent lives at the config top level, not under `parameters`. Default on@high
    # for reasoning models (matches Chat); user can disable it in module settings.
    if model.capabilities.reasoning:
        cfg = module_config.get_module_config('asking') or {}
        params['thinking'] = cfg.get('thinking') or DEFAULT_INTENT
    # Fingerprint includes tools + thinking so settings changes rebuild the provider.
    fingerprint = {**params, '_tools': sorted(tools)}
    return _provider_cache.get_or_create(
        model_id, fingerprint,
        lambda: create_model_provider(
            model.api_provider, model_id,
            LLMParameters(**params) if params else LLMParameters(),
            tools=tools,
        ),
    )


@router.get("/config")
async def get_config(username: str = Depends(get_auth_user)):
    """Return available models (reasoning-capable) + the module default."""
    models = model_manager.get_models(filter=module_config.get_model_filter('asking'))
    return {
        "models": [
            {"model_id": m.model_id, "name": f"{m.name}, {m.api_provider}"}
            for m in (models or [])
        ],
        "default_model": module_config.get_default_model('asking'),
    }


@router.post("/process")
async def process_asking(
    text: str = Form(...),
    history: str = Form("[]"),
    model_id: str = Form(None),
    custom_prompt: str = Form(""),
    files: List[UploadFile] = File(default=[]),
    run_id: str = Form(None),
    username: str = Depends(get_auth_user),
):
    """AG-UI SSE streaming endpoint for asking with thinking.

    The answer runs on its own (backend/api/runs.py): a dropped connection does not lose it, and the client
    can collect it again from /asking/resume with the `run_id` it sent.
    """
    import json
    run_id = run_id or str(uuid.uuid4())
    msg_id = str(uuid.uuid4())
    thinking_id = str(uuid.uuid4())

    if not text.strip():
        async def empty():
            yield _enc.encode(RunErrorEvent(message="Please provide a question."))
        return StreamingResponse(empty(), media_type="text/event-stream")

    # Parse history
    try:
        history_list = json.loads(history) if history else []
    except Exception:
        history_list = []

    # Save uploaded files
    file_paths = []
    for f in files:
        if f.filename:
            path, _ = await save_upload(f, username)
            file_paths.append(path)

    # Build content
    content_text = text
    if history_list:
        content_text = f"Previous interaction:\n{json.dumps(history_list, ensure_ascii=False)}\n\nFollow-up question:\n{text}"
    
    content = {"text": content_text}
    if file_paths:
        content["files"] = file_paths

    # Get model and system prompt
    mid = model_id or module_config.get_default_model('asking')
    sys_prompt = custom_prompt.strip() if custom_prompt and custom_prompt.strip() else SYSTEM_PROMPT

    async def event_stream():
        try:
            provider = _get_provider(mid)
            thread_id = f"asking-{username}"

            yield _enc.encode(RunStartedEvent(thread_id=thread_id, run_id=run_id))

            reply = ReplyEvents(msg_id, thinking_id)
            tool_seen: set = set()
            message = LLMMessage(role="user", content=content)

            async for chunk in aiter_sync(provider.generate_stream(
                messages=[message],
                system_prompt=sys_prompt,
            )):
                if not isinstance(chunk, dict):
                    continue

                if thinking := chunk.get('thinking'):
                    # BedrockConverse yields `thinking` as {text, signature}; AG-UI
                    # ReasoningMessageContentEvent.delta expects a plain string.
                    delta_text = thinking.get('text', '') if isinstance(thinking, dict) else str(thinking)
                    if not delta_text:
                        continue
                    for event in reply.reasoning(delta_text):
                        yield event

                # Surface tool calls as a one-line note in the reasoning block so
                # the UI shows progress instead of looking frozen during a search.
                if tool_use := chunk.get('tool_use'):
                    tc_id = tool_use.get('toolUseId')
                    name = tool_use.get('name')
                    if tc_id and name and tc_id not in tool_seen:
                        tool_seen.add(tc_id)
                        for event in reply.reasoning(f"\n🔧 Calling {name}…\n"):
                            yield event

                if c := chunk.get('content'):
                    if txt := c.get('text'):
                        for event in reply.text(txt):
                            yield event

            for event in reply.finish():
                yield event
            yield _enc.encode(RunFinishedEvent(thread_id=thread_id, run_id=run_id))

        except Exception as e:
            logger.error(f"Asking error for {username}: {e}", exc_info=True)
            yield _enc.encode(RunErrorEvent(**run_error_fields(e, "An error occurred.")))

    run = runs.start((username, _run_slot(run_id)), run_id, event_stream(), _run_error_event)
    return StreamingResponse(run.follow(0), media_type="text/event-stream", headers=_SSE_HEADERS)


@router.get("/resume")
async def resume_asking(run_id: str = Query(...), username: str = Depends(get_auth_user)):
    """Attach to an answer that is still running, or finished recently: all its events from the start."""
    run = runs.get((username, _run_slot(run_id)), run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found (it may have expired)")
    return StreamingResponse(run.follow(0), media_type="text/event-stream", headers=_SSE_HEADERS)
