"""Bridges the browser microphone to AWS Transcribe streaming over a WebSocket.

Client sends binary PCM 16 kHz mono frames; server sends back JSON text frames:
{"type": "partial"|"final", "text": ..., "lang": ...} or {"type": "error", ...}.
Client sends "__end__" to stop; server flushes the final, then closes.
"""
from __future__ import annotations

import asyncio
import json
import os
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from amazon_transcribe.client import TranscribeStreamingClient
from amazon_transcribe.handlers import TranscriptResultStreamHandler
from amazon_transcribe.model import TranscriptEvent

from backend.common.logger import setup_logger
from backend.core.config import env_config
from backend.common.sso import introspect as sso_introspect, SSOError

logger = setup_logger('api.transcribe')

router = APIRouter(prefix="/asking", tags=["asking"])


_SAMPLE_RATE = 16000  # AWS Transcribe requires PCM 16 kHz mono
_LANGUAGE_OPTIONS = ["zh-CN", "en-US"]  # auto-detected via identify_multiple_languages
# Pin near the server, not AWS_REGION (= us-west-2 for Bedrock), to cut latency.
_REGION = os.getenv('TRANSCRIBE_REGION', 'ap-southeast-1')


async def _authenticate_ws(ws: WebSocket) -> Optional[str]:
    """Validate the SSO cookie on the WebSocket handshake, return the user sub.

    SSO only — Cognito would need session middleware threaded through the
    WebSocket, which FastAPI doesn't do automatically.
    """
    if not env_config.sso_config['enabled']:
        await ws.close(code=1008, reason="voice input requires SSO mode")
        return None

    cookie_name = env_config.sso_config['cookie_name']
    sid = ws.cookies.get(cookie_name)
    if not sid:
        await ws.close(code=1008, reason="no SSO cookie")
        return None
    try:
        user = await sso_introspect(sid)
    except SSOError as e:
        logger.error(f"[transcribe] SSO introspection unavailable: {e}")
        await ws.close(code=1011, reason="auth service unavailable")
        return None
    if not user:
        await ws.close(code=1008, reason="session expired")
        return None
    return user.sub


class _Handler(TranscriptResultStreamHandler):
    """Push Transcribe events back over the WebSocket as JSON frames."""

    def __init__(self, output_stream, ws: WebSocket):
        super().__init__(output_stream)
        self._ws = ws

    async def handle_transcript_event(self, transcript_event: TranscriptEvent):
        for result in transcript_event.transcript.results:
            if not result.alternatives:
                continue
            text = result.alternatives[0].transcript
            if not text:
                continue
            payload = {
                "type": "partial" if result.is_partial else "final",
                "text": text,
                "lang": getattr(result, "language_code", None) or "",
            }
            try:
                await self._ws.send_text(json.dumps(payload, ensure_ascii=False))
            except Exception:
                # Client gone — let the surrounding task observe the disconnect.
                return


@router.websocket("/transcribe")
async def transcribe_ws(ws: WebSocket):
    await ws.accept()
    sub = await _authenticate_ws(ws)
    if not sub:
        return

    client = TranscribeStreamingClient(region=_REGION)
    try:
        stream = await client.start_stream_transcription(
            language_code=None,
            media_sample_rate_hz=_SAMPLE_RATE,
            media_encoding="pcm",
            identify_multiple_languages=True,
            language_options=_LANGUAGE_OPTIONS,
        )
    except Exception as e:
        logger.error(f"[transcribe] failed to open Transcribe stream: {e}", exc_info=True)
        try:
            await ws.send_text(json.dumps({"type": "error", "message": "transcribe unavailable"}))
        finally:
            await ws.close(code=1011)
        return

    handler = _Handler(stream.output_stream, ws)
    handler_task = asyncio.create_task(handler.handle_events())

    # "__end__" = graceful stop (flush + wait for final); disconnect = client
    # gone (nothing to flush to).
    client_gone = False

    try:
        while True:
            msg = await ws.receive()
            if msg.get("type") == "websocket.disconnect":
                client_gone = True
                break
            audio = msg.get("bytes")
            if audio:
                await stream.input_stream.send_audio_event(audio_chunk=audio)
                continue
            if msg.get("text") == "__end__":
                break
    except WebSocketDisconnect:
        client_gone = True
    except Exception as e:
        logger.error(f"[transcribe] WS loop error for {sub}: {e}", exc_info=True)
        client_gone = True

    # No more audio → AWS flushes one last `final`, then handle_events() returns.
    try:
        await stream.input_stream.end_stream()
    except Exception as e:
        logger.warning(f"[transcribe] end_stream() raised: {e}")

    if client_gone:
        handler_task.cancel()
    else:
        # Drain the trailing final BEFORE closing — closing early cancels AWS's
        # in-flight response. AWS returns it in ~100 ms; the client waits 10 s
        # so it never closes first.
        try:
            await asyncio.wait_for(handler_task, timeout=3.0)
        except asyncio.TimeoutError:
            logger.warning(f"[transcribe] final flush timed out for {sub}")
            handler_task.cancel()
        except Exception:
            handler_task.cancel()

    try:
        await asyncio.gather(handler_task, return_exceptions=True)
    except Exception:
        pass
    try:
        await ws.close()
    except Exception:
        pass
