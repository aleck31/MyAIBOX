"""Bridges the browser microphone to AWS Transcribe streaming over a WebSocket.

Client sends binary PCM 16 kHz mono frames; server sends back JSON text frames:
{"type": "partial"|"final", "text": ..., "lang": ...} or {"type": "error", ...}.
Client sends "__end__" to stop; server flushes the final, then closes.

Uses the official aws-sdk-transcribe-streaming (smithy) SDK; the old awslabs
amazon-transcribe package is deprecated and pinned awscrt to a version that
conflicts with Nova Sonic's bidi SDK.
"""
from __future__ import annotations

import asyncio
import json
import os
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from aws_sdk_transcribe_streaming.client import TranscribeStreamingClient
from aws_sdk_transcribe_streaming.config import Config
from aws_sdk_transcribe_streaming.models import (
    StartStreamTranscriptionInput,
    AudioEvent,
    AudioStreamAudioEvent,
)
from smithy_aws_core.identity.chain import create_default_chain
from smithy_http.aio.crt import AWSCRTHTTPClient

from backend.common.logger import setup_logger
from backend.core.config import env_config
from backend.common.sso import introspect as sso_introspect, SSOError

logger = setup_logger('api.transcribe')

router = APIRouter(prefix="/asking", tags=["asking"])


_SAMPLE_RATE = 16000  # AWS Transcribe requires PCM 16 kHz mono
# Comma-separated, NOT a list — aws-sdk-signers 0.3 can't sign a list-valued header
_LANGUAGE_OPTIONS = "zh-CN,en-US"  # auto-detected via identify_multiple_languages
# Pin near the server, not AWS_REGION (= us-west-2 for Bedrock), to cut latency.
_REGION = os.getenv('TRANSCRIBE_REGION', 'ap-southeast-1')


def _new_client() -> TranscribeStreamingClient:
    """Build a Transcribe streaming client using the default AWS credential chain."""
    transport = AWSCRTHTTPClient()
    config = Config(
        region=_REGION,
        aws_credentials_identity_resolver=create_default_chain(transport),
        transport=transport,
    )
    return TranscribeStreamingClient(config=config)


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


async def _pump_results(output_stream, ws: WebSocket) -> None:
    """Read transcript events from Transcribe and push them as JSON frames."""
    async for event in output_stream:
        # output_stream yields the TranscriptResultStream union; the transcript
        # variant carries .value: TranscriptEvent.
        transcript_event = getattr(event, "value", None)
        transcript = getattr(transcript_event, "transcript", None)
        if transcript is None:
            continue
        for result in (transcript.results or []):
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
                await ws.send_text(json.dumps(payload, ensure_ascii=False))
            except Exception:
                return  # client gone


@router.websocket("/transcribe")
async def transcribe_ws(ws: WebSocket):
    await ws.accept()
    sub = await _authenticate_ws(ws)
    if not sub:
        return

    client = _new_client()
    try:
        stream = await client.start_stream_transcription(
            input=StartStreamTranscriptionInput(
                media_sample_rate_hertz=_SAMPLE_RATE,
                media_encoding="pcm",
                identify_multiple_languages=True,
                language_options=_LANGUAGE_OPTIONS,
            )
        )
        _, output_stream = await stream.await_output()
    except Exception as e:
        logger.error(f"[transcribe] failed to open Transcribe stream: {e}", exc_info=True)
        try:
            await ws.send_text(json.dumps({"type": "error", "message": "transcribe unavailable"}))
        finally:
            await ws.close(code=1011)
        return

    pump_task = asyncio.create_task(_pump_results(output_stream, ws))

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
                await stream.input_stream.send(AudioStreamAudioEvent(value=AudioEvent(audio_chunk=audio)))
                continue
            if msg.get("text") == "__end__":
                break
    except WebSocketDisconnect:
        client_gone = True
    except Exception as e:
        logger.error(f"[transcribe] WS loop error for {sub}: {e}", exc_info=True)
        client_gone = True

    # No more audio → AWS flushes one last `final`, then the result pump ends.
    try:
        await stream.input_stream.close()
    except Exception as e:
        logger.warning(f"[transcribe] input close raised: {e}")

    if client_gone:
        pump_task.cancel()
    else:
        # Drain the trailing final BEFORE closing — closing early cancels AWS's
        # in-flight response. AWS returns it in ~100 ms; the client waits 10 s.
        try:
            await asyncio.wait_for(pump_task, timeout=3.0)
        except asyncio.TimeoutError:
            logger.warning(f"[transcribe] final flush timed out for {sub}")
            pump_task.cancel()
        except Exception:
            pump_task.cancel()

    await asyncio.gather(pump_task, return_exceptions=True)
    try:
        await ws.close()
    except Exception:
        pass
