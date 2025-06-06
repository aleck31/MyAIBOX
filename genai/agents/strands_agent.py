# Copyright iX.
# SPDX-License-Identifier: MIT-0
from typing import Dict, AsyncIterator, Optional
from core.logger import logger
from core.config import env_config
from strands import Agent
from strands.models import BedrockModel
from strands.models.anthropic import AnthropicModel
from strands.models.openai import OpenAIModel
from .custom_models import GeminiModel
from strands.tools.mcp import MCPClient
from mcp.client.streamable_http import streamablehttp_client
from genai.models.model_manager import model_manager
from genai.tools.tool_manager import tool_manager
from utils.aws import get_aws_session


class StrandsAgentProvider:
    """Provider for Strands Agents integration"""
    
    def __init__(self, model_id: str, system_prompt: str = ''):
        """Initialize Strands Agent provider

        Args:
            model_id: Model ID to use
            system_prompt: System prompt for the agent
        """
        self.model_id = model_id
        self.system_prompt = system_prompt
        self._mcp_client = None
        self._agent_cache = {}
        logger.debug(f"[StrandsAgentProvider] Initialized with model ID: {self.model_id}")
    
    def _get_strands_model(self):
        """Get Strands model based on API provider"""

        logger.debug(f"[StrandsAgentProvider] Getting model by ID: {self.model_id}")
        model = model_manager.get_model_by_id(self.model_id)
        logger.debug(f"[StrandsAgentProvider] Model API provider: {model.api_provider}")
        
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
                    logger.debug(f"[StrandsAgentProvider] Created BedrockModel with region: {bedrock_region}")
                    return model
                except Exception as e:
                    logger.error(f"[StrandsAgentProvider] Error creating BedrockModel: {str(e)}", exc_info=True)
                    raise
            case 'ANTHROPIC':
                return AnthropicModel(
                    client_args={
                        "api_key": "<KEY>",
                    },
                    # **model_config
                    max_tokens=1028,
                    model_id=self.model_id,
                    params={
                        "temperature": 0.7,
                    }
                )
            case 'OPENAI':
                return OpenAIModel(
                    client_args={
                        "api_key": "<KEY>",
                    },
                    # **model_config
                    model_id=self.model_id,
                    params={
                        "max_tokens": 1000,
                        "temperature": 0.7,
                    }
                )
            case _:
                pass

    def _get_mcp_client(self, mcp_server: str) -> Optional[MCPClient]:
        """Get or initialize MCP client for specified server
        
        Args:
            mcp_server: Name of the MCP server
            
        Returns:
            MCPClient instance or None if initialization fails
        """
        if self._mcp_client is None:
            try:
                # Get server configuration from tool_manager
                server_config = tool_manager.get_mcp_tools(mcp_server)
                
                if not server_config:
                    logger.error(f"[StrandsAgentProvider] {mcp_server} server configuration not found")
                    return None
                
                if server_config.get("disabled", False):
                    logger.warning(f"[StrandsAgentProvider] {mcp_server} server is disabled")
                    return None
                
                # Initialize MCP client with URL from configuration
                server_url = server_config.get("url")
                if not server_url:
                    logger.error(f"[StrandsAgentProvider] {mcp_server} server URL not found in configuration")
                    return None
                
                self._mcp_client = MCPClient(
                    lambda: streamablehttp_client(server_url)
                )
                logger.info(f"[StrandsAgentProvider] Initialized MCP client for {mcp_server}")
            except Exception as e:
                logger.error(f"[StrandsAgentProvider] Failed to initialize MCP client: {str(e)}")
                self._mcp_client = None
        
        return self._mcp_client

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

        logger.debug(f"[StrandsAgentProvider] Calling agent with prompt: {prompt}")
        async for event in agent.stream_async(prompt):
            # logger.debug(f"[StrandsAgentProvider] Streaming event: {event}")
            if 'event' in event:
                # 1. Handle messageStart events (role information)
                if 'messageStart' in event['event']:
                    event_loop+=1
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
                    logger.debug(f"[StrandsAgentProvider] The {event_loop} round(s) of event loop ends.")
                continue

    async def generate_stream(self, prompt: str, mcp_server: str = None) -> AsyncIterator[Dict]:
        """Generate content using Strands Agent
        
        Args:
            prompt: User prompt
            mcp_server: Optional name of the MCP server to use
            
        Returns:
            AsyncIterator of structured events with content and metadata
        """
        try:
            import json
            logger.debug(f"[StrandsAgentProvider] Generating content for: {prompt}")

            # Create model
            model = self._get_strands_model()

            # Check if we need to use MCP tools
            if mcp_server and (mcp_client := self._get_mcp_client(mcp_server)):
                # Store the MCP client as an instance variable to keep it alive
                self._active_mcp_client = mcp_client
                
                # Use the MCP client as a context manager to keep the session active
                # during the entire agent execution
                with mcp_client:
                    # Get the tools from the MCP server
                    tools = mcp_client.list_tools_sync()
                    logger.debug(f"[StrandsAgentProvider] Got {len(tools)} tools from MCP server")
                    
                    # Create an agent with these tools and the specified model
                    agent = Agent(
                        tools=tools,
                        system_prompt=self.system_prompt,
                        model=model
                    )
                    logger.info(f"[StrandsAgentProvider] Initialized Strands Agent with MCP tools")
                    
                    # Process events within the MCP client context
                    async for event_data in self._process_events(agent, prompt):
                        yield event_data
            else:
                # Create agent without tools if no MCP server specified or MCP client initialization failed
                if not mcp_server:
                    logger.warning(f"[StrandsAgentProvider] No MCP server specified, tools will not be available")
                else:
                    logger.warning(f"[StrandsAgentProvider] Failed to get MCP client for {mcp_server}")
                
                agent = Agent(system_prompt=self.system_prompt, model=model)
                logger.debug(f"[StrandsAgentProvider] Running agent without MCP tools")
                
                # Process events without MCP tools
                async for event_data in self._process_events(agent, prompt):
                    yield event_data
            
        except Exception as e:
            logger.error(f"[StrandsAgentProvider] Error during content generation: {str(e)}", exc_info=True)
            raise
