"""Talk (realtime voice) end-to-end against real Nova Sonic + Polly + tools.

Nova Sonic is speech-to-speech and ignores plain text input, so we synthesize the
question with Polly (16 kHz PCM) and stream it like a mic — with trailing silence so
the model's endpointing/VAD detects end-of-speech. Verifies the tool-use chain: the
model invokes get_weather and answers from the (date-normalized) tool result.
"""
from __future__ import annotations

import asyncio
import base64

import boto3
import pytest

from backend.api.prompts.talk import BUILTIN_TALK_AGENTS, build_prompt
from backend.genai.agents.live_provider import LiveAgentProvider
from backend.genai.models.model_manager import model_manager

pytestmark = pytest.mark.integration

NOVA_SONIC = "amazon.nova-2-sonic-v1:0"


@pytest.fixture(scope="module", autouse=True)
def _init_models():
    model_manager.init_default_models()


def _synth_pcm(text: str, region: str = "ap-southeast-1") -> bytes:
    polly = boto3.client("polly", region_name=region)
    r = polly.synthesize_speech(Text=text, OutputFormat="pcm", SampleRate="16000", VoiceId="Joanna")
    return r["AudioStream"].read()


async def _ask_with_voice(question: str, enabled_tools: list) -> dict:
    """Drive a LiveAgentProvider with synthesized speech; collect tool use + reply."""
    if not model_manager.get_model_by_id(NOVA_SONIC):
        pytest.skip("Nova Sonic not in the model registry for this environment")

    agent = BUILTIN_TALK_AGENTS["english-coach"]
    prov = LiveAgentProvider(
        model_id=NOVA_SONIC,
        system_prompt=build_prompt(agent.prompt, "adult", enabled_tools),
        voice_id="matthew",
        tool_config={"enabled": bool(enabled_tools), "legacy_tools": enabled_tools},
    )
    await prov.start()
    out: dict = {"tool_uses": [], "text": []}

    async def collect():
        async for ev in prov.events():
            t = ev.get("type") if isinstance(ev, dict) else None
            if t == "tool_use_stream":
                tu = ev.get("current_tool_use") or {}
                if tu.get("name"):
                    out["tool_uses"].append(tu["name"])
            elif t == "bidi_transcript_stream" and ev.get("role") == "assistant":
                out["text"].append(ev.get("text", ""))

    task = asyncio.create_task(collect())
    try:
        pcm = _synth_pcm(question)
        for i in range(0, len(pcm), 2048):
            await prov.send_audio(base64.b64encode(pcm[i:i + 2048]).decode())
            await asyncio.sleep(0.02)
        for _ in range(60):  # ~1.2s trailing silence → end-of-speech
            await prov.send_audio(base64.b64encode(b"\x00" * 2048).decode())
            await asyncio.sleep(0.02)
        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=30)
        except asyncio.TimeoutError:
            pass
    finally:
        task.cancel()
        await prov.destroy()
    out["text"] = "".join(out["text"]).strip()
    return out


async def test_talk_tool_use_weather():
    """Voice question needing real data → model calls get_weather and answers from it."""
    res = await _ask_with_voice("What will the weather be in Tokyo tomorrow?", ["get_weather"])
    assert "get_weather" in res["tool_uses"], f"model did not call get_weather: {res}"
    # Answer should reflect the tool result (a temperature in °C / degrees).
    assert any(k in res["text"].lower() for k in ("°c", "degree", "celsius")), \
        f"reply did not use the weather result: {res['text']!r}"
