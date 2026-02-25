# Copyright iX.
# SPDX-License-Identifier: MIT-0
import uuid
from typing import Literal
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from ag_ui.core import (
    RunStartedEvent, RunFinishedEvent, RunErrorEvent,
    TextMessageStartEvent, TextMessageContentEvent, TextMessageEndEvent,
    BaseEvent, EventType,
)
from ag_ui.encoder import EventEncoder
from core.service.service_factory import ServiceFactory
from api.auth import get_auth_user
from api.prompts.text import SYSTEM_PROMPTS, STYLES, LANG_MAP
from common.logger import setup_logger

logger = setup_logger('api.text')

router = APIRouter(prefix="/text", tags=["text"])

_gen_service = None
_enc = EventEncoder()

# Operations available for text processing
TEXT_OPERATIONS = {
    "proofread": "Proofreading ✍️",
    "rewrite": "Rewrite 🔄",
    "reduce": "Reduction ✂️",
    "expand": "Expansion 📝",
}

LANGS = list(LANG_MAP.keys())
STYLE_KEYS = list(STYLES.keys())


def get_gen_service():
    global _gen_service
    if _gen_service is None:
        _gen_service = ServiceFactory.create_gen_service('text')
    return _gen_service


class TextRequest(BaseModel):
    text: str
    operation: str  # proofread | rewrite | reduce | expand
    target_lang: str = "en_US"
    style: str | None = None  # only for rewrite


@router.get("/config")
async def get_config(username: str = Depends(get_auth_user)):
    """Return available operations, languages, and styles."""
    return {
        "operations": [
            {"key": k, "label": v} for k, v in TEXT_OPERATIONS.items()
        ],
        "languages": LANGS,
        "styles": STYLE_KEYS,
    }


@router.post("/process")
async def process_text(
    body: TextRequest,
    username: str = Depends(get_auth_user),
):
    """AG-UI SSE streaming endpoint for text processing."""
    run_id = str(uuid.uuid4())
    message_id = str(uuid.uuid4())

    if not body.text.strip():
        async def empty():
            yield _enc.encode(RunErrorEvent(message="Please provide some text to process."))
        return StreamingResponse(empty(), media_type="text/event-stream")

    # Build system prompt
    target_lang = LANG_MAP.get(body.target_lang, "English")
    operation = body.operation

    if operation == "rewrite":
        style_key = body.style or "正常"
        style_instruction = f"Follow this style: {STYLES.get(style_key, STYLES['正常'])['prompt']}"
        system_prompt = SYSTEM_PROMPTS["rewrite"].format(
            target_lang=target_lang, style_instruction=style_instruction
        )
    else:
        system_prompt = SYSTEM_PROMPTS.get(operation, SYSTEM_PROMPTS["proofread"]).format(
            target_lang=target_lang
        )

    async def event_stream():
        try:
            service = get_gen_service()
            thread_id = f"text-{username}"

            yield _enc.encode(RunStartedEvent(thread_id=thread_id, run_id=run_id))
            yield _enc.encode(TextMessageStartEvent(message_id=message_id, role="assistant"))

            result = await service.gen_text_stateless(
                content={"text": f"<text>\n{body.text}\n</text>"},
                system_prompt=system_prompt,
            )

            # Emit full result as single content event
            yield _enc.encode(TextMessageContentEvent(message_id=message_id, delta=result))
            yield _enc.encode(TextMessageEndEvent(message_id=message_id))
            yield _enc.encode(RunFinishedEvent(thread_id=thread_id, run_id=run_id))

        except Exception as e:
            logger.error(f"Text process error for {username}: {e}", exc_info=True)
            yield _enc.encode(RunErrorEvent(message="An error occurred while processing your text."))

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
