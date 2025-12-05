# Copyright iX.
# SPDX-License-Identifier: MIT-0
from typing import Dict, AsyncIterator, Optional, List
from contextlib import ExitStack
from common.logger import logger
from core.config import env_config
from strands import Agent
from strands.models import BedrockModel
from strands.models.openai import OpenAIModel
from strands.agent.conversation_manager import SlidingWindowConversationManager
from utils.aws import get_aws_session
from genai.models.model_manager import model_manager
from genai.tools.provider import tool_provider
from genai.agents.chunk_builder import create_text_chunk, create_tool_chunk


class AgentProvider:
    """Simplified Strands Agents Provider using native features"""
    
    def __init__(self, model_id: str, system_prompt: str = ''):
        self.model_id = model_id
        self.system_prompt = system_prompt
    
    def _get_strands_model(self):
        """Get Strands model based on API provider"""
        model = model_manager.get_model_by_id(self.model_id)
        if not model:
            raise ValueError(f"Model {self.model_id} not found")
        
        if model.api_provider.upper() == 'BEDROCK':
            session = get_aws_session(region_name=env_config.bedrock_config['region_name'])
            return BedrockModel(model_id=self.model_id, boto_session=session)
        elif model.api_provider.upper() == 'OPENAI':
            return OpenAIModel(
                client_args={"api_key": "<KEY>"},
                model_id=self.model_id,
                params={"max_tokens": 1000, "temperature": 0.7}
            )
        raise ValueError(f"Unsupported provider: {model.api_provider}")

    async def generate_stream(
        self, 
        prompt: str, 
        history_messages: Optional[List] = None,
        tool_config: Optional[Dict] = None
    ) -> AsyncIterator[Dict]:
        """Unified streaming generation using Strands native features"""
        try:
            model = self._get_strands_model()
            tool_config = tool_config or {}
            
            # Get tools
            all_tools = []
            mcp_clients = []
            if tool_config.get('enabled', True):
                base_tools, mcp_clients = tool_provider.get_tools_and_contexts({
                    'include_legacy': tool_config.get('include_legacy', True),
                    'mcp_tools_enabled': tool_config.get('mcp_tools_enabled', False),
                    'strands_tools_enabled': tool_config.get('strands_tools_enabled', True)
                })
                all_tools = base_tools
            
            # Handle MCP context if needed
            if mcp_clients:
                with ExitStack() as stack:
                    for client in mcp_clients:
                        try:
                            stack.enter_context(client)
                            all_tools.extend(client.list_tools_sync())
                        except Exception as e:
                            logger.warning(f"Failed to load MCP tools: {e}")
                    
                    agent = self._create_agent(model, all_tools, history_messages)
                    async for chunk in self._stream_events(agent, prompt):
                        yield chunk
            else:
                agent = self._create_agent(model, all_tools, history_messages)
                async for chunk in self._stream_events(agent, prompt):
                    yield chunk
                        
        except Exception as e:
            logger.error(f"Generation error: {e}", exc_info=True)
            yield {"text": f"Error: {str(e)}", "metadata": {"error": True}}

    def _create_agent(self, model, tools, history_messages):
        """Create Strands Agent with native features"""
        return Agent(
            tools=tools or None,
            system_prompt=self.system_prompt,
            model=model,
            messages=history_messages or [],
            callback_handler=None,  # Use null handler for custom processing
            conversation_manager=SlidingWindowConversationManager(window_size=40)
        )

    async def _stream_events(self, agent, prompt: str) -> AsyncIterator[Dict]:
        """Stream and convert Strands events to our format"""
        tool_state = {}  # Track: {tool_use_id: {name, params}}
        
        async for event in agent.stream_async(prompt):
            if chunk := self._convert_event(event, tool_state):
                yield chunk

    def _convert_event(self, event: Dict, tool_state: Dict) -> Optional[Dict]:
        """Convert Strands event to our format"""
        # Text streaming
        if 'data' in event:
            return create_text_chunk(event['data'])
        
        # Tool execution - current_tool_use indicates tool is running
        if 'current_tool_use' in event:
            tool_use = event['current_tool_use']
            if tool_use.get('name'):
                tool_use_id = tool_use.get('toolUseId', 'unknown')
                # Ensure params is a dict
                params = tool_use.get('input', {})
                if isinstance(params, str):
                    try:
                        import json
                        params = json.loads(params)
                    except:
                        params = {'input': params}
                
                # Store state for completion event
                tool_state[tool_use_id] = {
                    'name': tool_use['name'],
                    'params': params
                }
                
                return create_tool_chunk(tool_use['name'], params, 'running', tool_use_id=tool_use_id)
        
        # Tool result - message with toolResult indicates completion
        if 'message' in event:
            msg = event['message']
            if msg.get('role') == 'user' and 'content' in msg:
                for content in msg['content']:
                    if 'toolResult' in content:
                        result_data = content['toolResult']
                        tool_use_id = result_data.get('toolUseId', 'unknown')
                        
                        # Get stored tool state
                        state = tool_state.get(tool_use_id, {})
                        tool_name = state.get('name', 'unknown')
                        tool_params = state.get('params', {})
                        
                        # Extract result text
                        result_text = ''
                        if 'content' in result_data:
                            for item in result_data['content']:
                                if 'text' in item:
                                    result_text = item['text']
                                    break
                        
                        # Determine status
                        status = 'completed' if result_data.get('status') == 'success' else 'failed'
                        
                        # Clean up state
                        tool_state.pop(tool_use_id, None)

                        return create_tool_chunk(
                            tool_name,
                            tool_params,
                            status,
                            result_text,
                            tool_use_id=tool_use_id
                        )
        
        # Metadata
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

    async def reload_tools(self):
        """Reload all tools"""
        await tool_provider.reload_tools()
