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
)
from ag_ui.encoder import EventEncoder
from core.module_config import module_config
from genai.models.model_manager import model_manager
from genai.models.providers import LLMMessage, LLMParameters, create_model_provider
from api.auth import get_auth_user
from webui.modules.vision.prompts import VISION_SYSTEM_PROMPT
from common.logger import setup_logger

logger = setup_logger('api.vision')

router = APIRouter(prefix="/vision", tags=["vision"])

_enc = EventEncoder()
_provider_cache = {}

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets/uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


def _get_provider(model_id: str):
    if model_id not in _provider_cache:
        model = model_manager.get_model_by_id(model_id)
        if not model:
            raise ValueError(f"Model not found: {model_id}")
        params = module_config.get_inference_params('vision') or {}
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
    """Return available vision models."""
    models = model_manager.get_models(filter={'category': 'vision'})
    return {
        "models": [
            {"model_id": m.model_id, "name": f"{m.name}, {m.api_provider}"}
            for m in (models or [])
        ],
    }


@router.post("/analyze")
async def analyze_vision(
    text: str = Form(""),
    model_id: str = Form(None),
    files: List[UploadFile] = File(default=[]),
    username: str = Depends(get_auth_user),
):
    """AG-UI SSE streaming endpoint for vision analysis."""
    run_id = str(uuid.uuid4())
    msg_id = str(uuid.uuid4())

    # Save uploaded files
    file_paths = []
    for f in files:
        if f.filename:
            path = await _save_file(f)
            file_paths.append(path)

    if not file_paths:
        async def empty():
            yield _enc.encode(RunErrorEvent(message="Please provide an image or document to analyze."))
        return StreamingResponse(empty(), media_type="text/event-stream")

    # Build content
    user_text = text.strip() if text else "Describe the media or document in detail."
    content = {"text": user_text, "files": file_paths}

    mid = model_id or module_config.get_default_model('vision')

    async def event_stream():
        try:
            provider = _get_provider(mid)
            thread_id = f"vision-{username}"

            yield _enc.encode(RunStartedEvent(thread_id=thread_id, run_id=run_id))
            yield _enc.encode(TextMessageStartEvent(message_id=msg_id, role="assistant"))

            message = LLMMessage(role="user", content=content)

            for chunk in provider.generate_stream(
                messages=[message],
                system_prompt=VISION_SYSTEM_PROMPT,
            ):
                if not isinstance(chunk, dict):
                    continue
                if c := chunk.get('content'):
                    if txt := c.get('text'):
                        yield _enc.encode(TextMessageContentEvent(message_id=msg_id, delta=txt))

            yield _enc.encode(TextMessageEndEvent(message_id=msg_id))
            yield _enc.encode(RunFinishedEvent(thread_id=thread_id, run_id=run_id))

        except Exception as e:
            logger.error(f"Vision error for {username}: {e}", exc_info=True)
            yield _enc.encode(RunErrorEvent(message="An error occurred during analysis."))

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
