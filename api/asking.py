# Copyright iX.
# SPDX-License-Identifier: MIT-0
import os
import uuid
from typing import List
from fastapi import APIRouter, Depends, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from ag_ui.core import (
    RunStartedEvent, RunFinishedEvent, RunErrorEvent,
    TextMessageStartEvent, TextMessageContentEvent, TextMessageEndEvent,
    ReasoningMessageStartEvent, ReasoningMessageContentEvent, ReasoningMessageEndEvent,
)
from ag_ui.encoder import EventEncoder
from core.module_config import module_config
from genai.models.model_manager import model_manager
from genai.models.providers import LLMMessage, LLMParameters, create_model_provider
from api.auth import get_auth_user
from webui.modules.asking.prompts import SYSTEM_PROMPT
from common.logger import setup_logger

logger = setup_logger('api.asking')

router = APIRouter(prefix="/asking", tags=["asking"])

_enc = EventEncoder()
_provider_cache = {}

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets/uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


def _get_provider(model_id: str):
    if model_id not in _provider_cache:
        model = model_manager.get_model_by_id(model_id)
        if not model:
            raise ValueError(f"Model not found: {model_id}")
        params = module_config.get_inference_params('asking') or {}
        llm_params = LLMParameters(**params) if params else LLMParameters()
        _provider_cache[model_id] = create_model_provider(model.api_provider, model_id, llm_params)
    return _provider_cache[model_id]


async def _save_file(f: UploadFile) -> str:
    ext = os.path.splitext(f.filename or "")[1].lower()
    file_id = f"{uuid.uuid4().hex}{ext}"
    path = os.path.join(UPLOAD_DIR, file_id)
    content = await f.read()
    with open(path, "wb") as out:
        out.write(content)
    return path


@router.get("/config")
async def get_config(username: str = Depends(get_auth_user)):
    """Return available models (reasoning-capable)."""
    models = model_manager.get_models(filter={'reasoning': True})
    return {
        "models": [
            {"model_id": m.model_id, "name": f"{m.name}, {m.api_provider}"}
            for m in (models or [])
        ],
    }


@router.post("/process")
async def process_asking(
    text: str = Form(...),
    history: str = Form("[]"),
    model_id: str = Form(None),
    custom_prompt: str = Form(""),
    files: List[UploadFile] = File(default=[]),
    username: str = Depends(get_auth_user),
):
    """AG-UI SSE streaming endpoint for asking with thinking."""
    import json
    run_id = str(uuid.uuid4())
    msg_id = str(uuid.uuid4())
    thinking_id = str(uuid.uuid4())

    if not text.strip():
        async def empty():
            yield _enc.encode(RunErrorEvent(message="Please provide a question."))
        return StreamingResponse(empty(), media_type="text/event-stream")

    # Parse history
    try:
        history_list = json.loads(history) if history else []
    except:
        history_list = []

    # Save uploaded files
    file_paths = []
    for f in files:
        if f.filename:
            path = await _save_file(f)
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

            thinking_started = False
            text_started = False
            message = LLMMessage(role="user", content=content)

            for chunk in provider.generate_stream(
                messages=[message],
                system_prompt=sys_prompt,
            ):
                if not isinstance(chunk, dict):
                    continue

                if thinking := chunk.get('thinking'):
                    if not thinking_started:
                        yield _enc.encode(ReasoningMessageStartEvent(message_id=thinking_id, role="assistant"))
                        thinking_started = True
                    yield _enc.encode(ReasoningMessageContentEvent(message_id=thinking_id, delta=thinking))
                
                if c := chunk.get('content'):
                    if txt := c.get('text'):
                        if thinking_started and not text_started:
                            yield _enc.encode(ReasoningMessageEndEvent(message_id=thinking_id))
                        if not text_started:
                            yield _enc.encode(TextMessageStartEvent(message_id=msg_id, role="assistant"))
                            text_started = True
                        yield _enc.encode(TextMessageContentEvent(message_id=msg_id, delta=txt))

            if thinking_started and not text_started:
                yield _enc.encode(ReasoningMessageEndEvent(message_id=thinking_id))
            if text_started:
                yield _enc.encode(TextMessageEndEvent(message_id=msg_id))
            yield _enc.encode(RunFinishedEvent(thread_id=thread_id, run_id=run_id))

        except Exception as e:
            logger.error(f"Asking error for {username}: {e}", exc_info=True)
            yield _enc.encode(RunErrorEvent(message="An error occurred."))

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
