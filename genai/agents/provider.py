# Copyright iX.
# SPDX-License-Identifier: MIT-0
from typing import Dict, AsyncIterator, Optional, List
from core.logger import logger
from core.config import env_config
from strands import Agent
from strands.models import BedrockModel
from strands.models.openai import OpenAIModel
from utils.aws import get_aws_session
from genai.models.model_manager import model_manager
from genai.tools.provider  import tool_provider, ToolType
from genai.agents.resp_format import create_text_chunk, create_tool_chunk, create_file_chunk


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
    
    def _get_agent_cache_key(self, tools_enabled: bool, tool_filter: Optional[List[str]], include_mcp: bool, include_legacy: bool) -> str:
        """Generate cache key for agent instances"""
        key_parts = [
            self.model_id,
            self.system_prompt,
            str(tools_enabled),
            str(sorted(tool_filter) if tool_filter else "all"),
            str(include_mcp),
            str(include_legacy)
        ]
        return "|".join(key_parts)

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

    def _parse_tool_metrics(self, metrics_obj) -> Optional[Dict]:
        """Parse tool metrics from event_loop_metrics
        
        Args:
            metrics_obj: EventLoopMetrics object or string representation
            
        Returns:
            Dict with tool information or None if no tools found
        """
        try:
            # Convert to string if it's an object
            metrics_str = str(metrics_obj)
            
            # Log the full metrics for debugging
            logger.debug(f"[AgentProvider] Full tool metrics: {metrics_str}")
            
            # Extract tool metrics using regex (since it's a string representation)
            import re
            
            # Look for tool_metrics pattern - updated to capture result
            tool_pattern = r"'(\w+)': ToolMetrics\(tool=\{'toolUseId': '([^']+)', 'name': '([^']+)', 'input': (\{[^}]*\})\}, call_count=(\d+), success_count=(\d+), error_count=(\d+)(?:, total_time=([^,)]+))?"
            
            match = re.search(tool_pattern, metrics_str)
            if match:
                tool_name = match.group(1)
                tool_use_id = match.group(2)
                tool_display_name = match.group(3)
                tool_input_str = match.group(4)
                call_count = int(match.group(5))
                success_count = int(match.group(6))
                error_count = int(match.group(7))
                
                # Parse tool input (basic parsing)
                try:
                    import ast
                    tool_params = ast.literal_eval(tool_input_str)
                except:
                    tool_params = {}
                
                # Determine status based on counts
                if error_count > 0:
                    status = "failed"
                elif success_count > 0:
                    status = "completed"
                else:
                    status = "running"
                
                # For now, we can't extract the actual result from EventLoopMetrics
                # The result is handled separately by Strands and passed to the LLM
                # We'll indicate that the tool completed successfully
                result = f"Tool '{tool_display_name}' completed successfully" if status == "completed" else None
                
                logger.debug(f"[AgentProvider] Parsed tool: {tool_display_name}, status: {status}, result: {result}")
                
                return {
                    "name": tool_display_name,
                    "params": tool_params,
                    "status": status,
                    "result": result,
                    "id": tool_use_id,
                    "call_count": call_count,
                    "success_count": success_count,
                    "error_count": error_count
                }
            
        except Exception as e:
            logger.debug(f"[AgentProvider] Could not parse tool metrics: {str(e)}")
        
        return None

    def _standardize_chunk(self, raw_event: Dict) -> Optional[Dict]:
        """Convert raw Strands event to standard agent response format
        
        Args:
            raw_event: Raw event from Strands agent
            
        Returns:
            Standardized response chunk or None if event should be skipped
        """
        # PRIORITY 1: Handle Strands simplified format (contains more metadata)
        if 'data' in raw_event and 'delta' in raw_event:
            text_delta = raw_event['delta'].get('text', '')
            if text_delta:
                # Also check for tool usage information in the same event
                tool_info = None
                if 'event_loop_metrics' in raw_event:
                    tool_info = self._parse_tool_metrics(raw_event['event_loop_metrics'])
                
                result = create_text_chunk(text_delta)
                
                # Add tool information if available
                if tool_info:
                    result['tool_use'] = {
                        "name": tool_info['name'],
                        "params": tool_info['params'],
                        "status": tool_info['status'],
                        "result": tool_info.get('result')
                    }
                
                return result
        
        # PRIORITY 2: Handle metadata events (usage statistics, etc.)
        elif 'event' in raw_event and 'metadata' in raw_event['event']:
            return {"metadata": raw_event['event']['metadata']}
        
        # PRIORITY 3: Handle message stop events
        elif 'event' in raw_event and 'messageStop' in raw_event['event']:
            return {"metadata": {"stop_reason": raw_event['event']['messageStop'].get('stopReason')}}
        
        # PRIORITY 4: Handle tool result messages
        elif 'message' in raw_event:
            message = raw_event['message']
            # Check if this is a tool result message
            if (isinstance(message, dict) and 
                message.get('role') == 'user' and 
                'content' in message):
                
                content = message['content']
                if isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict) and 'toolResult' in item:
                            tool_result = item['toolResult']
                            logger.debug(f"[AgentProvider] Found toolResult: {tool_result}")
                            
                            # Extract tool information from the result
                            if isinstance(tool_result, dict):
                                tool_use_id = tool_result.get('toolUseId', 'unknown')
                                status = tool_result.get('status', 'completed')
                                
                                # Parse the content to extract the actual tool result
                                result_data = None
                                if 'content' in tool_result and isinstance(tool_result['content'], list):
                                    for content_item in tool_result['content']:
                                        if isinstance(content_item, dict) and 'text' in content_item:
                                            try:
                                                # The text contains a string representation of the actual result
                                                import ast
                                                result_data = ast.literal_eval(content_item['text'])
                                                break
                                            except:
                                                result_data = content_item['text']
                                
                                # Extract tool name and file path from result data
                                tool_name = 'unknown'
                                file_path = None
                                
                                if isinstance(result_data, dict):
                                    file_path = result_data.get('file_path')
                                    # Try to infer tool name from the result or use a default
                                    if file_path and 'img_' in file_path:
                                        tool_name = 'generate_image'
                                
                                # Create a tool result chunk with the actual result data
                                return create_tool_chunk(
                                    tool_name, 
                                    {}, 
                                    status, 
                                    result_data
                                )
            
            # Skip other message events since we've been streaming chunks
            return None
        
        # SKIP: Bedrock native events (to avoid duplicates with Strands format)
        elif 'event' in raw_event and 'contentBlockDelta' in raw_event['event']:
            # Skip this to avoid duplicates - we handle the Strands format above
            return None
        
        # LEGACY: Handle tool usage information from event_loop_metrics (standalone)
        elif 'event_loop_metrics' in raw_event and 'data' not in raw_event:
            tool_info = self._parse_tool_metrics(raw_event['event_loop_metrics'])
            if tool_info:
                return create_tool_chunk(
                    tool_info['name'], 
                    tool_info['params'], 
                    tool_info['status'],
                    tool_info.get('result')
                )
        
        # LEGACY: Handle legacy formats for backward compatibility
        elif 'content' in raw_event and 'text' in raw_event['content']:
            # Try to parse JSON string in text field (legacy format)
            import json
            try:
                event_data = json.loads(raw_event['content']['text'])
                
                if 'event' in event_data and 'contentBlockDelta' in event_data['event']:
                    delta = event_data['event']['contentBlockDelta'].get('delta', {})
                    if 'text' in delta:
                        return create_text_chunk(delta['text'])
                        
            except (json.JSONDecodeError, KeyError):
                # If it's not JSON, treat as plain text
                return create_text_chunk(raw_event['content']['text'])
        
        # LEGACY: Handle tool use from delta events (existing logic)
        elif 'tool_use' in raw_event:
            tool_info = raw_event['tool_use']
            tool_name = tool_info.get('name', 'unknown')
            tool_params = tool_info.get('input', {})
            
            if 'result' in tool_info:
                status = "completed"
                result = str(tool_info['result'])
            else:
                status = "running"
                result = None

            return create_tool_chunk(tool_name, tool_params, status, result)
        
        # LEGACY: Handle current_tool_use from delta (existing logic)
        elif 'delta' in raw_event and 'current_tool_use' in raw_event['delta']:
            tool_info = raw_event['delta']['current_tool_use']
            tool_name = tool_info.get('name', 'unknown')
            tool_params = tool_info.get('input', {})

            return create_tool_chunk(tool_name, tool_params, "running")
        
        # Handle file generation from tool results
        elif 'file_path' in raw_event:
            file_path = raw_event['file_path']
            import os
            _, ext = os.path.splitext(file_path.lower())
            
            if ext in ['.py', '.js', '.html', '.css', '.java', '.cpp', '.c', '.go', '.rs']:
                file_type = "code"
                language = ext[1:]
            elif ext in ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.svg']:
                file_type = "image"
                language = None
            elif ext in ['.mp3', '.wav', '.ogg', '.m4a']:
                file_type = "audio"
                language = None
            elif ext in ['.md', '.txt', '.doc', '.docx', '.pdf']:
                file_type = "document"
                language = None
            else:
                file_type = "file"
                language = None

            return create_file_chunk(file_path, file_type, language)
        
        # Skip events that don't contain useful content
        return None

    async def _process_events(self, agent, prompt: str) -> AsyncIterator[Dict]:
        """Process events from the agent and standardize the format
        
        Args:
            agent: Strands Agent instance
            prompt: User prompt
            
        Returns:
            AsyncIterator of standardized agent response chunks
        """
        logger.debug(f"[AgentProvider] Processing events for prompt: {prompt}")
        
        try:
            async for event in agent.stream_async(prompt):
                # Log ALL raw events for debugging
                logger.debug(f"[AgentProvider] Raw event: {event}")
                logger.debug(f"[AgentProvider] Raw event type: {type(event)}")
                logger.debug(f"[AgentProvider] Raw event keys: {list(event.keys()) if isinstance(event, dict) else 'Not a dict'}")
                
                # Standardize the raw event to our format
                standardized_chunk = self._standardize_chunk(event)
                
                if standardized_chunk is not None:
                    logger.debug(f"[AgentProvider] Yielding chunk: {list(standardized_chunk.keys())}")
                    yield standardized_chunk
                    
        except Exception as e:
            logger.error(f"[AgentProvider] Error processing events: {str(e)}", exc_info=True)
            # Yield error information
            yield {
                "text": f"Error processing response: {str(e)}",
                "metadata": {"error": True, "error_message": str(e)}
            }

    async def generate_stream(
        self, 
        prompt: str, 
        history_messages: Optional[List] = None,
        tool_config: Optional[Dict] = None
    ) -> AsyncIterator[Dict]:
        """Unified streaming generation method
        
        Args:
            prompt: User prompt
            history_messages: Optional list of Strands Message objects for context (None for single-turn)
            tool_config: Optional tool configuration dict with keys:
                - enabled: bool (default True)
                - include_legacy: bool (default True) 
                - include_mcp: bool (default True)
                - tool_filter: List[str] (optional specific tools)
            
        Returns:
            AsyncIterator of structured events with content and metadata
        """
        logger.debug(f"[AgentProvider] Generate stream with {len(history_messages) if history_messages else 0} history messages")
        
        # Use unified generation logic
        async for chunk in self._generate_with_agent(prompt, history_messages, tool_config):
            yield chunk

    async def _generate_with_agent(
        self, 
        prompt: str, 
        history_messages: Optional[List] = None,
        tool_config: Optional[Dict] = None
    ) -> AsyncIterator[Dict]:
        """Unified agent generation logic
        
        Args:
            prompt: User prompt
            history_messages: Optional list of Strands Message objects for context
            tool_config: Optional tool configuration
            
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
                            
                            # Get MCP client from tool config - fix attribute access
                            if hasattr(tool_info, 'config') and tool_info.config and 'tool_object' in tool_info.config:
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
                            
                            # Create agent with tools and optional history
                            agent = Agent(
                                tools=tools,
                                system_prompt=self.system_prompt,
                                model=model,
                                messages=history_messages  # Add history support
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
                            model=model,
                            messages=history_messages  # Add history support
                        )
                        logger.info(f"[AgentProvider] Initialized Strands Agent with {len(tools)} tools (Python only)")
                        
                        # Process events
                        async for event_data in self._process_events(agent, prompt):
                            yield event_data
                    
                except Exception as e:
                    logger.error(f"[AgentProvider] Error loading tools: {str(e)}", exc_info=True)
                    logger.warning(f"[AgentProvider] Tool loading failed, specific error: {type(e).__name__}: {str(e)}")
                    # Fallback to no tools
                    agent = Agent(
                        system_prompt=self.system_prompt, 
                        model=model,
                        messages=history_messages  # Add history support
                    )
                    logger.warning(f"[AgentProvider] Falling back to agent without tools")
                    
                    async for event_data in self._process_events(agent, prompt):
                        yield event_data
            else:
                # Tools disabled, create agent without tools
                agent = Agent(
                    system_prompt=self.system_prompt, 
                    model=model,
                    messages=history_messages  # Add history support
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
                        'package': tool.config.get('package') if hasattr(tool, 'config') and tool.config else None
                    }
                    for tool in legacy_tools
                ],
                'mcp': [
                    {
                        'name': tool.name,
                        'description': tool.description,
                        'enabled': tool.enabled,
                        'server': tool.config.get('server') if hasattr(tool, 'config') and tool.config else None
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
