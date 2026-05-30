# Copyright iX.
# SPDX-License-Identifier: MIT-0
"""Realtime voice agent provider — the speech sibling of AgentProvider.

Wraps Strands' experimental BidiAgent (bidirectional, full-duplex) the same way
AgentProvider wraps strands.Agent. The underlying realtime model (Nova Sonic now,
Gemini Live / OpenAI Realtime later) is swappable via api_provider; everything
above this layer (api/voice WS, frontend) is model-agnostic.

It is a full agent (tool loop / barge-in / event routing built in), not a bare
model call — tools are loaded from the same tool_provider as AgentProvider.
"""
from typing import AsyncIterator, Dict, Optional

from strands.experimental.bidi.agent.agent import BidiAgent
from strands.experimental.bidi.models.nova_sonic import BidiNovaSonicModel
from strands.experimental.bidi.types.events import BidiAudioInputEvent

from backend.common.logger import logger
from backend.genai.models.model_manager import model_manager
from backend.genai.tools.provider import tool_provider

# Audio formats fixed by the model contract (Nova Sonic).
INPUT_SAMPLE_RATE = 16000


class LiveAgentProvider:
    """Per-connection realtime voice agent over a Strands BidiAgent."""

    def __init__(
        self,
        model_id: str,
        system_prompt: str = '',
        voice_id: str = 'matthew',
        tool_config: Optional[Dict] = None,
    ):
        self.model_id = model_id
        self.system_prompt = system_prompt
        self.voice_id = voice_id
        self.tool_config = tool_config or {}
        self._agent: Optional[BidiAgent] = None
        self._mcp_clients: list = []
        self._started = False

    def _get_live_model(self):
        """Build the bidirectional model for this model_id (region from the registry)."""
        model = model_manager.get_model_by_id(self.model_id)
        if not model:
            raise ValueError(f"Model {self.model_id} not found")
        provider = model.api_provider.upper()
        if provider == 'BEDROCKSONIC':
            region = model.region or 'us-east-1'  # Nova Sonic: us-east-1 only
            return BidiNovaSonicModel(
                model_id=self.model_id,
                provider_config={'audio': {'output': {'voiceId': self.voice_id}}},
                client_config={'region': region},
            )
        raise ValueError(f"Unsupported realtime provider: {model.api_provider}")

    def _load_tools(self) -> list:
        """Load tools via the shared tool_provider (same registry as AgentProvider)."""
        if not self.tool_config.get('enabled', False):
            return []
        forwarded = {
            'legacy_tools': self.tool_config.get('legacy_tools', []),
            'strands_tools_enabled': self.tool_config.get('strands_tools_enabled', False),
            'mcp_tools_enabled': self.tool_config.get('mcp_tools_enabled', False),
        }
        if 'builtin_tools' in self.tool_config:
            forwarded['builtin_tools'] = self.tool_config['builtin_tools']
        if 'mcp_servers' in self.tool_config:
            forwarded['mcp_servers'] = self.tool_config['mcp_servers']
        base_tools, mcp_clients = tool_provider.get_tools_and_contexts(forwarded)
        for client in mcp_clients:
            try:
                client.start()
                base_tools.extend(client.list_tools_sync())
                self._mcp_clients.append(client)
            except Exception as e:
                logger.warning(f"[LiveAgentProvider] MCP client start failed: {e}")
        return base_tools

    def _ensure_agent(self) -> BidiAgent:
        if self._agent is not None:
            return self._agent
        tools = self._load_tools()
        self._agent = BidiAgent(
            model=self._get_live_model(),
            tools=tools or None,
            system_prompt=self.system_prompt or None,
        )
        logger.info(f"[LiveAgentProvider] Created BidiAgent: model={self.model_id}, voice={self.voice_id}, tools={len(tools)}")
        return self._agent

    async def start(self) -> None:
        agent = self._ensure_agent()
        await agent.start()
        self._started = True

    async def send_audio(self, pcm_base64: str) -> None:
        """Send a base64-encoded 16 kHz PCM chunk to the model."""
        if not self._started or self._agent is None:
            return
        await self._agent.send(BidiAudioInputEvent(audio=pcm_base64, sample_rate=INPUT_SAMPLE_RATE))

    async def events(self) -> AsyncIterator:
        """Yield BidiOutputEvents (transcript / audio / interrupted / tool / error)."""
        if self._agent is None:
            return
        async for event in self._agent.receive():
            yield event

    async def stop(self) -> None:
        if self._agent is not None and self._started:
            try:
                await self._agent.stop()
            except Exception as e:
                logger.warning(f"[LiveAgentProvider] stop error: {e}")
        self._started = False
        for client in self._mcp_clients:
            try:
                client.stop(None, None, None)
            except Exception:
                pass
        self._mcp_clients.clear()
        self._agent = None
