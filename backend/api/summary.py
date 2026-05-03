# Copyright iX.
# SPDX-License-Identifier: MIT-0
import uuid
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from ag_ui.core import (
    RunStartedEvent, RunFinishedEvent, RunErrorEvent,
    TextMessageStartEvent, TextMessageContentEvent, TextMessageEndEvent,
)
from ag_ui.encoder import EventEncoder
from core.service.service_factory import ServiceFactory
from genai.models.model_manager import model_manager
from api.auth import get_auth_user
from api.prompts.summary import SYSTEM_PROMPT, build_user_prompt, LANG_MAP
from common.logger import setup_logger

logger = setup_logger('api.summary')

router = APIRouter(prefix="/summary", tags=["summary"])

_gen_service = None
_enc = EventEncoder()

LANGS = list(LANG_MAP.keys())


def get_gen_service():
    global _gen_service
    if _gen_service is None:
        _gen_service = ServiceFactory.create_gen_service('summary')
    return _gen_service


class SummaryRequest(BaseModel):
    text: str
    target_lang: str = "Original"
    model_id: str | None = None


@router.get("/config")
async def get_config(username: str = Depends(get_auth_user)):
    """Return available models and languages."""
    models = model_manager.get_models(filter={'tool_use': True})
    return {
        "models": [
            {"model_id": m.model_id, "name": f"{m.name}, {m.api_provider}"}
            for m in (models or [])
        ],
        "languages": LANGS,
    }


@router.post("/process")
async def process_summary(
    body: SummaryRequest,
    username: str = Depends(get_auth_user),
):
    """AG-UI SSE streaming endpoint for text summarization."""
    run_id = str(uuid.uuid4())
    message_id = str(uuid.uuid4())

    if not body.text.strip():
        async def empty():
            yield _enc.encode(RunErrorEvent(message="Please provide some text to summarize."))
        return StreamingResponse(empty(), media_type="text/event-stream")

    # Build system prompt
    lang = LANG_MAP.get(body.target_lang, body.target_lang)
    system_prompt = SYSTEM_PROMPT.format(target_lang=lang)
    user_prompt = build_user_prompt(body.text, body.target_lang)

    async def event_stream():
        try:
            service = get_gen_service()
            thread_id = f"summary-{username}"

            yield _enc.encode(RunStartedEvent(thread_id=thread_id, run_id=run_id))
            yield _enc.encode(TextMessageStartEvent(message_id=message_id, role="assistant"))

            result = await service.gen_text_stateless(
                content={"text": user_prompt},
                system_prompt=system_prompt,
            )

            yield _enc.encode(TextMessageContentEvent(message_id=message_id, delta=result))
            yield _enc.encode(TextMessageEndEvent(message_id=message_id))
            yield _enc.encode(RunFinishedEvent(thread_id=thread_id, run_id=run_id))

        except Exception as e:
            logger.error(f"Summary error for {username}: {e}", exc_info=True)
            yield _enc.encode(RunErrorEvent(message="An error occurred while summarizing."))

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
