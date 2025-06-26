# Copyright iX.
# SPDX-License-Identifier: MIT-0
from typing import Dict, AsyncIterator, Optional, List
from core.logger import logger
from core.config import env_config
from strands import Agent
from strands.models import BedrockModel
from strands.models.openai import OpenAIModel
from genai.models.model_manager import model_manager
from genai.tools.tool_provider import tool_provider, ToolType
from utils.aws import get_aws_session


class AgentProvider:
    """Provider for Strands Agents integration with Universal Tool Manager"""
    
    def __init__(self, model_id: str, system_prompt: str = ''):
        """Initialize Strands Agent provider

        Args:
            model_id: Model ID to use
            system_prompt: System prompt for the agent
        """
        self.model_id = model_id
        self.system_prompt = system_prompt
        self._agent_cache = {}
        logger.debug(f"[AgentProvider] Initialized with model ID: {self.model_id}")
    
    def _get_strands_model(self):
        """Get Strands model based on API provider"""

        logger.debug(f"[AgentProvider] Getting model by ID: {self.model_id}")
        model = model_manager.get_model_by_id(self.model_id)
        
        if model is None:
            logger.error(f"[AgentProvider] Model with ID {self.model_id} not found")
            raise ValueError(f"Model with ID {self.model_id} not found")
            
        logger.debug(f"[AgentProvider] Model API provider: {model.api_provider}")
        
        match model.api_provider.upper():
            case 'BEDROCK':
                try:
                    # Get AWS session with the correct region for Bedrock
                    bedrock_region = env_config.bedrock_config['region_name']
                    session = get_aws_session(region_name=bedrock_region)
                    # Create BedrockModel
                    model = BedrockModel(
                        model_id=self.model_id,
                        boto_session=session
                    )
                    logger.debug(f"[AgentProvider] Created BedrockModel with region: {bedrock_region}")
                    return model
                except Exception as e:
                    logger.error(f"[AgentProvider] Error creating BedrockModel: {str(e)}", exc_info=True)
                    raise
            case 'OPENAI':
                return OpenAIModel(
                    client_args={
                        "api_key": "<KEY>",
                    },
                    model_id=self.model_id,
                    params={
                        "max_tokens": 1000,
                        "temperature": 0.7,
                    }
                )
            case _:
                logger.error(f"[AgentProvider] Unsupported API provider: {model.api_provider}")
                raise ValueError(f"Unsupported API provider: {model.api_provider}")

    async def _process_events(self, agent, prompt: str) -> AsyncIterator[Dict]:
        """Process events from the agent
        
        Args:
            agent: Strands Agent instance
            prompt: User prompt
            
        Returns:
            AsyncIterator of structured events with content and metadata
        """
        # Track event info and metadata
        role = ''
        metadata = {}
        event_loop = 0

        logger.debug(f"[AgentProvider] Calling agent with prompt: {prompt}")
        async for event in agent.stream_async(prompt):
            if 'event' in event:
                # 1. Handle messageStart events (role information)
                if 'messageStart' in event['event']:
                    event_loop += 1
                    role = event['event']['messageStart']['role']
                    # Clear metadata at the start of each new loop
                    metadata.clear()
                    continue
                # 2. Handle contentBlockDelta events (text content)
                if 'contentBlockDelta' in event['event']:
                    delta = event['event']['contentBlockDelta'].get('delta', {})
                    if 'text' in delta:
                        yield {
                            'role': role,
                            'content': delta,
                            'metadata': metadata
                        }
                # 3. Handle messageStop events (stop reason)
                if 'messageStop' in event['event']:
                    if 'stopReason' in event['event']['messageStop']:
                        metadata['stop_reason'] = event['event']['messageStop']['stopReason']
                    continue
                # 4. Handle metadata events
                if 'metadata' in event['event']:
                    # Update metadata
                    metadata.update(event['event']['metadata'])
                    yield {
                        'role': role,
                        'metadata': metadata
                    }
            elif 'delta' in event:
                if 'current_tool_use' in event['delta']:
                    curr_tool_use = event['delta']['current_tool_use']
                    yield {
                        'role': role,
                        'tool_use': curr_tool_use,
                        'metadata': metadata
                    }
            # message typically appear at the end of each loop
            elif 'message' in event:
                if event['message']['role'] == 'assistant':
                    logger.debug(f"[AgentProvider] The {event_loop} round(s) of event loop ends.")
                continue

    async def generate_stream(self, prompt: str, tool_config: Optional[Dict] = None) -> AsyncIterator[Dict]:
        """Generate content using Strands Agent with Universal Tool Manager
        
        Args:
            prompt: User prompt
            tool_config: Optional tool configuration dict with keys:
                - enabled: bool (default True)
                - include_legacy: bool (default True) 
                - include_mcp: bool (default True)
                - tool_filter: List[str] (optional specific tools)
            
        Returns:
            AsyncIterator of structured events with content and metadata
        """
        try:
            logger.debug(f"[AgentProvider] Generating content for: {prompt}")

            # Create model
            model = self._get_strands_model()

            # Parse tool configuration
            if tool_config is None:
                tool_config = {}
            
            tools_enabled = tool_config.get('enabled', True)
            include_legacy = tool_config.get('include_legacy', True)
            include_mcp = tool_config.get('include_mcp', True)
            tool_filter = tool_config.get('tool_filter', None)

            # Get tools if enabled
            if tools_enabled:
                try:
                    # Initialize universal tool manager if not already done
                    await tool_provider.initialize()
                    
                    # Get active MCP clients for context management
                    active_mcp_clients = []
                    if include_mcp:
                        # Get MCP clients that need to be kept alive
                        mcp_tools = tool_provider.list_tools(ToolType.MCP)
                        mcp_clients_dict = {}
                        
                        for tool_info in mcp_tools:
                            if not tool_info.enabled:
                                continue
                            if tool_filter and tool_info.name not in tool_filter:
                                continue
                            
                            # Get MCP client from tool config
                            if tool_info.config and 'tool_object' in tool_info.config:
                                tool_obj = tool_info.config['tool_object']
                                if hasattr(tool_obj, 'mcp_client'):
                                    server_name = tool_info.config.get('server', 'unknown')
                                    mcp_clients_dict[server_name] = tool_obj.mcp_client
                        
                        active_mcp_clients = list(mcp_clients_dict.values())
                    
                    # Use MCP clients in context managers
                    if active_mcp_clients:
                        logger.info(f"[AgentProvider] Managing {len(active_mcp_clients)} MCP client contexts")
                        
                        # Use synchronous context managers for MCP clients
                        import contextlib
                        with contextlib.ExitStack() as stack:
                            # Enter all MCP client contexts (synchronous)
                            for mcp_client in active_mcp_clients:
                                stack.enter_context(mcp_client)
                            
                            # Now get tools with active MCP contexts
                            tools = await tool_provider.get_tools_for_agent(
                                tool_filter=tool_filter,
                                include_legacy=include_legacy,
                                include_mcp=include_mcp
                            )
                            
                            # Create agent with tools
                            agent = Agent(
                                tools=tools,
                                system_prompt=self.system_prompt,
                                model=model
                            )
                            logger.info(f"[AgentProvider] Initialized Strands Agent with {len(tools)} tools (MCP contexts active)")
                            
                            # Process events within MCP contexts
                            async for event_data in self._process_events(agent, prompt):
                                yield event_data
                    else:
                        # No MCP clients, proceed normally
                        tools = await tool_provider.get_tools_for_agent(
                            tool_filter=tool_filter,
                            include_legacy=include_legacy,
                            include_mcp=False  # No MCP tools available
                        )
                        
                        agent = Agent(
                            tools=tools,
                            system_prompt=self.system_prompt,
                            model=model
                        )
                        logger.info(f"[AgentProvider] Initialized Strands Agent with {len(tools)} tools (Python only)")
                        
                        # Process events
                        async for event_data in self._process_events(agent, prompt):
                            yield event_data
                    
                except Exception as e:
                    logger.error(f"[AgentProvider] Error loading tools: {str(e)}")
                    # Fallback to no tools
                    agent = Agent(
                        system_prompt=self.system_prompt, 
                        model=model
                    )
                    logger.warning(f"[AgentProvider] Falling back to agent without tools")
                    
                    async for event_data in self._process_events(agent, prompt):
                        yield event_data
            else:
                # Tools disabled, create agent without tools
                agent = Agent(
                    system_prompt=self.system_prompt, 
                    model=model
                )
                logger.info(f"[AgentProvider] Initialized Strands Agent without tools")
                
                # Process events
                async for event_data in self._process_events(agent, prompt):
                    yield event_data
            
        except Exception as e:
            logger.error(f"[AgentProvider] Error during content generation: {str(e)}", exc_info=True)
            raise

    async def get_available_tools(self) -> Dict[str, List[Dict]]:
        """Get information about available tools
        
        Returns:
            Dict with 'legacy' and 'mcp' keys containing tool information
        """
        try:
            await tool_provider.initialize()
            
            legacy_tools = tool_provider.list_tools(ToolType.LEGACY)
            mcp_tools = tool_provider.list_tools(ToolType.MCP)
            
            return {
                'legacy': [
                    {
                        'name': tool.name,
                        'description': tool.description,
                        'enabled': tool.enabled,
                        'package': tool.config.get('package') if tool.config else None
                    }
                    for tool in legacy_tools
                ],
                'mcp': [
                    {
                        'name': tool.name,
                        'description': tool.description,
                        'enabled': tool.enabled,
                        'server': tool.config.get('server') if tool.config else None
                    }
                    for tool in mcp_tools
                ]
            }
        except Exception as e:
            logger.error(f"[AgentProvider] Error getting available tools: {str(e)}")
            return {'legacy': [], 'mcp': []}

    def enable_tool(self, tool_name: str):
        """Enable a specific tool"""
        tool_provider.enable_tool(tool_name)

    def disable_tool(self, tool_name: str):
        """Disable a specific tool"""
        tool_provider.disable_tool(tool_name)

    async def reload_tools(self):
        """Reload all tools"""
        await tool_provider.reload_tools()
