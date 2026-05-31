"""Talk with Agent — realtime speech-to-speech over a WebSocket, per voice agent.

Mirrors the chat module: list voice agents, then open a realtime session for a
chosen agent (its persona prompt + voice). Client sends binary PCM 16 kHz mono
audio; server relays the BidiAgent's output as JSON frames:
  {"type": "transcript", "text", "role", "final"}
  {"type": "audio", "audio": <base64>, "sample_rate"}
  {"type": "interrupted"} | {"type": "error", "message"}
Client sends "__end__" or disconnects to stop.

Auth/relay only — the realtime agent (Nova Sonic now, others later) lives in
LiveAgentProvider; voice personas in talk_agent_registry.
"""
from __future__ import annotations

import asyncio
import base64
import json
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends

from backend.common.logger import setup_logger
from backend.core.module_config import module_config
from backend.core.talk_agents import talk_agent_registry
from backend.genai.models.model_manager import model_manager
from backend.genai.agents.live_provider import LiveAgentProvider
from backend.api.auth import get_auth_user
from backend.api.transcribe import _authenticate_ws  # reuse SSO WS auth

logger = setup_logger('api.talk')

router = APIRouter(prefix="/talk", tags=["talk"])

# Per-(user, talk-agent) provider cache (ARD 002): hang up pauses the BidiAgent
# but keeps it cached, so reconnecting resumes with the prior transcript as context.
import time
_TALK_TTL = 1800           # 30 min idle eviction (voice sessions are short-lived)
_talk_cache: dict = {}     # key -> (LiveAgentProvider, last_ts)


async def _get_or_create_provider(sub: str, agent_id: str, model_id: str, system_prompt: str,
                                   voice_id: str, tool_config: dict, history: list):
    """Resolve a voice session (ARD 002 priority): cached BidiAgent → reuse (it
    already holds the conversation); else build fresh, seeding it with `history`
    sent by the client (the front-end transcript the user hasn't cleared) so the
    agent resumes even after the cache TTL evicted the live session."""
    key = f"{sub}:{agent_id}"
    now = time.time()
    for k, (prov, ts) in list(_talk_cache.items()):  # evict idle
        if now - ts > _TALK_TTL:
            _talk_cache.pop(k, None)
            try:
                await prov.destroy()
            except Exception:
                pass
    entry = _talk_cache.get(key)
    if entry:
        provider, _ = entry
        provider.voice_id = voice_id  # honor a newly-picked voice on reconnect
        _talk_cache[key] = (provider, now)
        return provider
    provider = LiveAgentProvider(model_id=model_id, system_prompt=system_prompt,
                                 voice_id=voice_id, tool_config=tool_config, history=history)
    _talk_cache[key] = (provider, now)
    return provider


@router.delete("/session/{agent_id}")
async def clear_session(agent_id: str, username: str = Depends(get_auth_user)):
    """Clear the cached voice session so the agent forgets the prior conversation
    (front-end 'clear transcript' → back-end loses memory too, staying consistent)."""
    key = f"{username}:{agent_id}"
    entry = _talk_cache.pop(key, None)
    if entry:
        try:
            await entry[0].destroy()
        except Exception:
            pass
    return {"ok": True}


def _agent_dto(a) -> dict:
    return {"id": a.id, "name": a.name, "description": a.description,
            "avatar": a.avatar, "voice_id": a.voice_id}


@router.get("/config")
async def get_config(username: str = Depends(get_auth_user)):
    """Realtime models + module default + voice options (for the section bar)."""
    models = model_manager.get_models(filter=module_config.get_model_filter('talk'))
    return {
        "models": [{"model_id": m.model_id, "name": f"{m.name}, {m.api_provider}"} for m in (models or [])],
        "default_model": module_config.get_default_model('talk'),
        "voices": [
            {"id": "matthew", "name": "Matthew (US, male)"},
            {"id": "tiffany", "name": "Tiffany (US, female)"},
            {"id": "amy", "name": "Amy (UK, female)"},
        ],
    }


@router.get("/agents")
async def list_agents(username: str = Depends(get_auth_user)):
    """List the available voice agents (sidebar)."""
    return {"agents": [_agent_dto(a) for a in talk_agent_registry.list_agents()]}


@router.get("/agents/{agent_id}")
async def get_agent(agent_id: str, username: str = Depends(get_auth_user)):
    try:
        return _agent_dto(talk_agent_registry.get_agent(agent_id))
    except KeyError:
        return {"error": f"Unknown voice agent: {agent_id}"}


def _to_frame(event) -> Optional[dict]:
    """Translate a BidiOutputEvent into a compact client JSON frame (or None to skip)."""
    etype = event.get("type") if isinstance(event, dict) else None
    if etype == "bidi_transcript_stream":
        return {"type": "transcript", "text": event.get("text", ""),
                "role": event.get("role", "assistant"), "final": bool(event.get("is_final"))}
    if etype == "bidi_audio_stream":
        return {"type": "audio", "audio": event.get("audio", ""),
                "sample_rate": event.get("sample_rate", 16000)}
    if etype == "bidi_interruption":
        return {"type": "interrupted"}
    if etype == "bidi_error":
        return {"type": "error", "message": str(event.get("message", "error"))}
    return None  # connection/usage/complete events not surfaced to the client


_VOICES = {"matthew", "tiffany", "amy"}


@router.websocket("/stream/{agent_id}")
async def talk_ws(ws: WebSocket, agent_id: str):
    await ws.accept()
    sub = await _authenticate_ws(ws)
    if not sub:
        return

    try:
        agent = talk_agent_registry.get_agent(agent_id)
    except KeyError:
        await ws.send_text(json.dumps({"type": "error", "message": f"unknown agent: {agent_id}"}))
        await ws.close(code=1008)
        return

    # Caller may override the agent's default voice via ?voice_id=
    voice_id = ws.query_params.get("voice_id")
    if voice_id not in _VOICES:
        voice_id = agent.voice_id

    model_id = agent.default_model or module_config.get_default_model('talk')
    tool_config = {'enabled': bool(agent.enabled_tools), 'legacy_tools': agent.enabled_tools}

    # First client frame is a setup frame carrying the front-end transcript the user
    # hasn't cleared: {type:"start", history:[{role,text}...]}. Used to seed a fresh
    # session when the cache was evicted (cache hit ignores it — it already has the convo).
    history = []
    try:
        data = json.loads(await ws.receive_text())
        if data.get("type") == "start":
            for h in (data.get("history") or [])[-40:]:
                text = (h.get("text") or "").strip()
                if text:
                    history.append({"role": "assistant" if h.get("role") == "assistant" else "user",
                                    "content": [{"text": text}]})
    except Exception:
        pass

    # Per-(user, agent) session cache (ARD 002): reuse cached BidiAgent (resumes the
    # conversation); else build fresh seeded with the client history.
    provider = await _get_or_create_provider(sub, agent_id, model_id, agent.prompt, voice_id, tool_config, history)

    try:
        await provider.start()
    except Exception as e:
        logger.error(f"[talk] failed to start {agent_id} for {sub}: {e}", exc_info=True)
        try:
            await ws.send_text(json.dumps({"type": "error", "message": "voice unavailable"}))
        finally:
            await ws.close(code=1011)
        return

    async def pump_events() -> None:
        try:
            async for event in provider.events():
                frame = _to_frame(event)
                if frame is None:
                    continue
                try:
                    await ws.send_text(json.dumps(frame, ensure_ascii=False))
                except Exception:
                    return
        except Exception as e:
            logger.warning(f"[talk] event pump ended for {sub}: {e}")

    pump_task = asyncio.create_task(pump_events())

    try:
        while True:
            msg = await ws.receive()
            if msg.get("type") == "websocket.disconnect":
                break
            audio = msg.get("bytes")
            if audio:
                await provider.send_audio(base64.b64encode(audio).decode("ascii"))
                continue
            if msg.get("text") == "__end__":
                break
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"[talk] WS loop error for {sub}: {e}", exc_info=True)

    pump_task.cancel()
    await asyncio.gather(pump_task, return_exceptions=True)
    # Hang up = pause (keep the cached BidiAgent + its messages for resume within TTL);
    # full teardown happens on idle eviction. cloud_sync OFF: nothing persisted, by design.
    await provider.pause()
    try:
        await ws.close()
    except Exception:
        pass
