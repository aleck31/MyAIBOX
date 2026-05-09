# Copyright iX.
# SPDX-License-Identifier: MIT-0
from typing import Dict, AsyncIterator, Optional, List
from backend.common.logger import logger
from backend.core.config import env_config
from strands import Agent
from strands.models import BedrockModel
from strands.models.openai import OpenAIModel
from strands.models.gemini import GeminiModel
from strands.agent.conversation_manager import SlidingWindowConversationManager
from backend.utils.aws import get_aws_session, get_secret
from backend.genai.models.model_manager import model_manager
from backend.genai.tools.provider import tool_provider
from backend.genai.agents.chunk_builder import create_text_chunk, create_tool_chunk, create_thinking_chunk


class AgentProvider:
    """Strands Agent provider with cached Agent instance and MCP connections."""

    def __init__(
        self,
        model_id: str,
        system_prompt: str = '',
        tool_config: Optional[Dict] = None,
        skills: Optional[List] = None,
    ):
        self.model_id = model_id
        self.system_prompt = system_prompt
        self.tool_config = tool_config or {}
        # Strands `Skill` objects; wrapped into an AgentSkills plugin at
        # Agent creation. Empty list = no plugin injected.
        self.skills: List = list(skills or [])
        self._agent: Optional[Agent] = None
        self._mcp_clients: list = []
        # HTTP clients shared across model swaps so update_model() does not
        # leak sockets. Bedrock reuses a module-level boto3 session already.
        self._openai_client = None
        self._gemini_client = None

    def _get_strands_model(self, model_id: Optional[str] = None):
        """Get Strands model based on API provider"""
        mid = model_id or self.model_id
        model = model_manager.get_model_by_id(mid)
        if not model:
            raise ValueError(f"Model {mid} not found")

        api_provider = model.api_provider.upper()

        if api_provider == 'BEDROCK':
            session = get_aws_session(region_name=env_config.bedrock_config['region_name'])
            kwargs = {"model_id": mid, "boto_session": session}
            if model.capabilities.reasoning:
                kwargs["additional_request_fields"] = {
                    "thinking": {"type": "enabled", "budget_tokens": 4096}
                }
            return BedrockModel(**kwargs)

        elif api_provider == 'OPENAI':
            if self._openai_client is None:
                from openai import OpenAI
                openai_secret_id = env_config.openai_config.get('secret_id')
                api_key = get_secret(openai_secret_id).get('api_key') if openai_secret_id else None
                self._openai_client = OpenAI(api_key=api_key)
            return OpenAIModel(
                client=self._openai_client,
                model_id=mid,
                params={"max_tokens": 1000, "temperature": 0.7},
            )

        elif api_provider == 'GEMINI':
            if self._gemini_client is None:
                from google import genai as google_genai
                gemini_secret_id = env_config.gemini_config.get('secret_id')
                api_key = get_secret(gemini_secret_id).get('api_key') if gemini_secret_id else None
                if not api_key:
                    raise ValueError("Gemini API key not configured")
                self._gemini_client = google_genai.Client(api_key=api_key)
            return GeminiModel(
                client=self._gemini_client,
                model_id=mid,
                params={"max_tokens": 8192, "temperature": 0.7},
            )

        raise ValueError(f"Unsupported provider: {model.api_provider}")

    def _load_tools(self) -> list:
        """Load tools and start MCP clients. Returns tool list."""
        all_tools = []
        if not self.tool_config.get('enabled', True):
            return all_tools

        # Forward both the explicit per-agent name lists (`builtin_tools`,
        # `mcp_servers`) and the older boolean fallbacks so ToolProvider can
        # pick the right branch. Without forwarding `builtin_tools`, callers
        # who opt out of e.g. `speak` would silently get every builtin tool.
        forwarded_config = {
            'legacy_tools': self.tool_config.get('legacy_tools', []),
            'strands_tools_enabled': self.tool_config.get('strands_tools_enabled', True),
            'mcp_tools_enabled': self.tool_config.get('mcp_tools_enabled', False),
        }
        if 'builtin_tools' in self.tool_config:
            forwarded_config['builtin_tools'] = self.tool_config['builtin_tools']
        if 'mcp_servers' in self.tool_config:
            forwarded_config['mcp_servers'] = self.tool_config['mcp_servers']
        base_tools, mcp_clients = tool_provider.get_tools_and_contexts(forwarded_config)
        all_tools = base_tools

        # Start MCP clients and collect tools (persistent, not context manager)
        for client in mcp_clients:
            try:
                client.start()
                all_tools.extend(client.list_tools_sync())
                self._mcp_clients.append(client)
                logger.debug("Started MCP client, tools loaded")
            except Exception as e:
                logger.warning(f"Failed to start MCP client: {e}")

        return all_tools

    def _ensure_agent(self, history_messages: Optional[List] = None) -> Agent:
        """Get cached Agent or create a new one."""
        if self._agent is not None:
            return self._agent

        model = self._get_strands_model()
        tools = self._load_tools()

        plugins = []
        if self.skills:
            from strands.vended_plugins.skills import AgentSkills
            plugins.append(AgentSkills(skills=self.skills))

        agent_kwargs = dict(
            tools=tools or None,
            system_prompt=self.system_prompt,
            model=model,
            messages=history_messages or [],
            callback_handler=None,
            conversation_manager=SlidingWindowConversationManager(window_size=40),
        )
        if plugins:
            agent_kwargs["plugins"] = plugins

        self._agent = Agent(**agent_kwargs)
        msg_count = len(history_messages) if history_messages else 0
        logger.info(
            f"[AgentProvider] Created Agent: model={self.model_id}, "
            f"history={msg_count}, tools={len(tools)}, skills={len(self.skills)}"
        )
        return self._agent

    def update_model(self, model_id: str):
        """Switch model without rebuilding Agent."""
        if self._agent is None:
            self.model_id = model_id
            return
        self.model_id = model_id
        self._agent.model = self._get_strands_model(model_id)
        logger.info(f"[AgentProvider] Model switched to {model_id}")

    def reload_tools(self):
        """Reload tools and MCP connections."""
        self._stop_mcp_clients()
        if self._agent is not None:
            tools = self._load_tools()
            self._agent.tool_registry.registry.clear()
            self._agent.tool_registry.dynamic_tools.clear()
            if tools:
                self._agent.tool_registry.process_tools(tools)
            logger.info(f"[AgentProvider] Tools reloaded: {len(tools)}")

    def destroy(self):
        """Cleanup Agent, MCP connections, and shared HTTP clients."""
        self._stop_mcp_clients()
        if self._agent is not None:
            try:
                self._agent.tool_registry.cleanup()
            except Exception as e:
                logger.warning(f"Agent cleanup error: {e}")
            self._agent = None
        if self._openai_client is not None:
            try:
                self._openai_client.close()
            except Exception as e:
                logger.warning(f"OpenAI client close error: {e}")
            self._openai_client = None
        # google-genai Client exposes no close(); drop the reference and let GC handle it.
        self._gemini_client = None
        logger.debug("[AgentProvider] Destroyed")

    def _stop_mcp_clients(self):
        """Stop all cached MCP clients."""
        for client in self._mcp_clients:
            try:
                client.stop(None, None, None)
            except Exception as e:
                logger.warning(f"MCP client stop error: {e}")
        self._mcp_clients.clear()

    @property
    def messages(self) -> List:
        """Get current Agent conversation messages."""
        return self._agent.messages if self._agent else []

    async def generate_stream(
        self,
        prompt: str,
        history_messages: Optional[List] = None,
        tool_config: Optional[Dict] = None,
    ) -> AsyncIterator[Dict]:
        """Stream generation using cached Agent instance."""
        try:
            # Update tool_config if provided (for first-time init)
            if tool_config and not self.tool_config:
                self.tool_config = tool_config

            agent = self._ensure_agent(history_messages)

            tool_state = {}
            async for event in agent.stream_async(prompt):
                if chunk := self._convert_event(event, tool_state):
                    yield chunk

        except Exception as e:
            logger.error(f"Generation error: {e}", exc_info=True)
            yield {"text": f"Error: {str(e)}", "metadata": {"error": True}}

    def _convert_event(self, event: Dict, tool_state: Dict) -> Optional[Dict]:
        """Convert Strands event to our format"""
        if 'data' in event:
            return create_text_chunk(event['data'])

        # Reasoning/thinking events
        if event.get('reasoning') and 'reasoningText' in event:
            return create_thinking_chunk(event['reasoningText'])

        if 'current_tool_use' in event:
            tool_use = event['current_tool_use']
            if tool_use.get('name'):
                tool_use_id = tool_use.get('toolUseId', 'unknown')
                params = tool_use.get('input', {})
                if isinstance(params, str):
                    try:
                        import json
                        params = json.loads(params)
                    except Exception:
                        params = {'input': params}

                tool_state[tool_use_id] = {'name': tool_use['name'], 'params': params}
                return create_tool_chunk(tool_use['name'], params, 'running', tool_use_id=tool_use_id)

        if 'message' in event:
            msg = event['message']
            if msg.get('role') == 'user' and 'content' in msg:
                for content in msg['content']:
                    if 'toolResult' in content:
                        result_data = content['toolResult']
                        tool_use_id = result_data.get('toolUseId', 'unknown')
                        state = tool_state.get(tool_use_id, {})
                        tool_name = state.get('name', 'unknown')
                        tool_params = state.get('params', {})

                        result_text = ''
                        if 'content' in result_data:
                            for item in result_data['content']:
                                if 'text' in item:
                                    result_text = item['text']
                                    break

                        status = 'completed' if result_data.get('status') == 'success' else 'failed'
                        tool_state.pop(tool_use_id, None)
                        return create_tool_chunk(tool_name, tool_params, status, result_text, tool_use_id=tool_use_id)

        if 'metadata' in event:
            return {"metadata": event['metadata']}

        return None

    async def get_available_tools(self) -> Dict[str, List[Dict]]:
        """Get information about available tools"""
        try:
            tools_info = tool_provider.list_tools()
            return {
                'legacy': [t for t in tools_info if t['type'] == 'legacy'],
                'strands': [t for t in tools_info if t['type'] == 'strands'],
                'mcp': [t for t in tools_info if t['type'] == 'mcp_server']
            }
        except Exception as e:
            logger.error(f"Error getting tools: {e}")
            return {'legacy': [], 'strands': [], 'mcp': []}
