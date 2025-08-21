# Copyright iX.
# SPDX-License-Identifier: MIT-0
from typing import Dict, AsyncIterator, Optional, List
from common.logger import logger
from core.config import env_config
from strands import Agent
from strands.models import BedrockModel
from strands.models.openai import OpenAIModel
from utils.aws import get_aws_session
from genai.models.model_manager import model_manager
from genai.tools.provider import tool_provider
from genai.agents.resp_format import create_text_chunk, create_tool_chunk, create_file_chunk


class ToolExecutionTracker:
    """Helper class to track tool execution status"""
    
    def __init__(self):
        self.active_tools = {}  # tool_use_id -> tool_info
        self.completed_tools = []
    
    def start_tool(self, tool_use_id: str, tool_name: str, tool_input: str):
        """Record tool execution start"""
        # Check if this tool is already being tracked to prevent duplicates
        if tool_use_id not in self.active_tools:
            self.active_tools[tool_use_id] = {
                'name': tool_name,
                'input': tool_input,
                'status': 'running'
            }
            logger.debug(f"[ToolTracker] Tool started: {tool_name} (ID: {tool_use_id})")
            return True  # New tool started
        else:
            # Tool already tracked, just update input if it's more complete
            existing_input = self.active_tools[tool_use_id]['input']
            if len(tool_input) > len(existing_input):
                self.active_tools[tool_use_id]['input'] = tool_input
                logger.debug(f"[ToolTracker] Tool input updated: {tool_name} (ID: {tool_use_id})")
            return False  # Tool already exists
    
    def finish_tool(self, tool_use_id: str, status: str = 'completed', result: Optional[str] = None):
        """Record tool execution completion"""
        if tool_use_id in self.active_tools:
            tool_info = self.active_tools.pop(tool_use_id)
            tool_info['status'] = status
            tool_info['result'] = result
            self.completed_tools.append(tool_info)
            logger.debug(f"[ToolTracker] Tool completed: {tool_info['name']} (Status: {status})")
            return tool_info
        return None
    
    def get_active_tool(self, tool_use_id: str):
        """Get active tool information"""
        return self.active_tools.get(tool_use_id)
    
    def has_active_tools(self):
        """Check if there are any running tools"""
        return len(self.active_tools) > 0


class AgentProvider:
    """Improved Strands Agents Provider"""
    
    def __init__(self, model_id: str, system_prompt: str = ''):
        """Initialize Strands Agent provider

        Args:
            model_id: Model ID to use
            system_prompt: System prompt for the agent
        """
        self.model_id = model_id
        self.system_prompt = system_prompt
        self._agent_cache = {}
        self.tool_tracker = ToolExecutionTracker()
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
                    client_args={"api_key": "<KEY>"},
                    model_id=self.model_id,
                    params={"max_tokens": 1000, "temperature": 0.7}
                )
            case _:
                logger.error(f"[AgentProvider] Unsupported API provider: {model.api_provider}")
                raise ValueError(f"Unsupported API provider: {model.api_provider}")

    def _handle_text_event(self, event: Dict) -> Optional[Dict]:
        """Handle text events"""
        if 'data' in event and 'delta' in event:
            text_delta = event['delta'].get('text', '')
            if text_delta:
                return create_text_chunk(text_delta)
        return None

    def _handle_tool_start_event(self, event: Dict) -> Optional[Dict]:
        """Handle tool execution start events"""
        if 'current_tool_use' in event:
            tool_info = event['current_tool_use']
            tool_use_id = tool_info.get('toolUseId', 'unknown')
            tool_name = tool_info.get('name', 'unknown')
            tool_input = tool_info.get('input', '')
            
            # Record tool execution start and only return event if it's a new tool
            is_new_tool = self.tool_tracker.start_tool(tool_use_id, tool_name, tool_input)
            
            if is_new_tool:
                # Return tool start event only for new tools
                return create_tool_chunk(tool_name, tool_input, 'running')
        return None

    def _handle_tool_result_event(self, event: Dict) -> Optional[Dict]:
        """Handle tool result events"""
        if 'message' in event:
            message = event['message']
            if (isinstance(message, dict) and 
                message.get('role') == 'user' and 
                'content' in message):
                
                content = message['content']
                if isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict) and 'toolResult' in item:
                            tool_result = item['toolResult']
                            tool_use_id = tool_result.get('toolUseId', 'unknown')
                            status = tool_result.get('status', 'completed')
                            
                            # Parse tool result
                            result_data = None
                            if 'content' in tool_result and isinstance(tool_result['content'], list):
                                for content_item in tool_result['content']:
                                    if isinstance(content_item, dict) and 'text' in content_item:
                                        try:
                                            import ast
                                            result_data = ast.literal_eval(content_item['text'])
                                            break
                                        except:
                                            result_data = content_item['text']
                            
                            # Complete tool execution tracking
                            tool_info = self.tool_tracker.finish_tool(tool_use_id, status, result_data)
                            
                            if tool_info:
                                # Ensure result is a string for create_tool_chunk
                                result_str = str(result_data) if result_data is not None else ""
                                return create_tool_chunk(
                                    tool_info['name'], 
                                    tool_info['input'], 
                                    status, 
                                    result_str
                                )
        return None

    def _handle_metadata_event(self, event: Dict) -> Optional[Dict]:
        """Handle metadata events"""
        if 'event' in event:
            if 'metadata' in event['event']:
                return {"metadata": event['event']['metadata']}
            elif 'messageStop' in event['event']:
                return {"metadata": {"stop_reason": event['event']['messageStop'].get('stopReason')}}
        return None

    def _standardize_chunk(self, raw_event: Dict) -> Optional[Dict]:
        """Convert raw Strands event to standard agent response format
        
        Uses clear event handling logic to avoid complex conditional statements
        """
        # 1. Handle text events (most common)
        text_chunk = self._handle_text_event(raw_event)
        if text_chunk:
            return text_chunk
        
        # 2. Handle tool start events
        tool_start_chunk = self._handle_tool_start_event(raw_event)
        if tool_start_chunk:
            return tool_start_chunk
        
        # 3. Handle tool result events
        tool_result_chunk = self._handle_tool_result_event(raw_event)
        if tool_result_chunk:
            return tool_result_chunk
        
        # 4. Handle metadata events
        metadata_chunk = self._handle_metadata_event(raw_event)
        if metadata_chunk:
            return metadata_chunk
        
        # 5. Skip events that don't need processing
        skip_events = [
            'init_event_loop', 'start_event_loop', 'start',
            'event_loop_metrics', 'agent', 'event_loop_parent_span',
            'event_loop_cycle_id', 'request_state', 'event_loop_cycle_trace',
            'event_loop_cycle_span', 'event_loop_parent_cycle_id'
        ]
        
        if any(key in raw_event for key in skip_events):
            return None
        
        # 6. Skip Bedrock native events (avoid duplicates)
        if 'event' in raw_event and 'contentBlockDelta' in raw_event['event']:
            return None
        
        # 7. Log unhandled events (for debugging)
        if logger.isEnabledFor(10):  # DEBUG level is 10
            logger.debug(f"[AgentProvider] Unhandled event keys: {list(raw_event.keys())}")
        return None

    async def _generate_with_mcp_context(self, prompt: str, base_tools: List, mcp_clients: List, model, history_messages):
        """Generate response with MCP context management
        
        Args:
            prompt: User prompt
            base_tools: Non-MCP tools (legacy + strands)
            mcp_clients: List of MCP clients requiring context management
            model: Strands model instance
            history_messages: Conversation history
        """
        from contextlib import ExitStack
        
        with ExitStack() as stack:
            all_tools = base_tools.copy()
            
            # Enter all MCP client contexts
            for client in mcp_clients:
                try:
                    stack.enter_context(client)
                    mcp_tools = client.list_tools_sync()
                    all_tools.extend(mcp_tools)  # Strands native mixed tool support!
                    logger.debug(f"[AgentProvider] Added {len(mcp_tools)} tools from MCP client")
                except Exception as e:
                    logger.warning(f"[AgentProvider] Failed to get tools from MCP client: {e}")
            
            # Create Agent with mixed tools - Strands handles everything natively!
            agent = Agent(
                tools=all_tools,
                system_prompt=self.system_prompt,
                model=model,
                messages=history_messages
            )
            logger.info(f"[AgentProvider] Initialized Strands Agent with {len(all_tools)} mixed tools")
            
            # Process events normally
            async for event_data in self._process_events(agent, prompt):
                yield event_data

    async def _process_events(self, agent, prompt: str) -> AsyncIterator[Dict]:
        """Process events from the agent and standardize the format"""
        logger.debug(f"[AgentProvider] Processing events for prompt: {prompt}")
        
        try:
            async for event in agent.stream_async(prompt):
                # Only log raw events in debug mode
                if logger.isEnabledFor(10):  # DEBUG level is 10
                    # logger.debug(f"[AgentProvider] Raw event keys: {list(event.keys()) if isinstance(event, dict) else 'Not a dict'}")
                    pass
                
                # Standardize event
                standardized_chunk = self._standardize_chunk(event)
                
                if standardized_chunk is not None:
                    # logger.debug(f"[AgentProvider] Yielding chunk: {list(standardized_chunk.keys())}")
                    yield standardized_chunk
                    
        except Exception as e:
            logger.error(f"[AgentProvider] Error processing events: {str(e)}", exc_info=True)
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
        """Unified streaming generation method"""
        if history_messages is not None:
            logger.debug(f"[AgentProvider] Generate stream with {len(history_messages)} history messages")

        try:
            logger.debug(f"[AgentProvider] Generating content for: {prompt}")

            # Reset tool tracker
            self.tool_tracker = ToolExecutionTracker()

            # Create model
            model = self._get_strands_model()

            # Parse tool configuration
            if tool_config is None:
                tool_config = {}
            
            tools_enabled = tool_config.get('enabled', True)
            include_legacy = tool_config.get('include_legacy', True)
            mcp_tools_enabled = tool_config.get('mcp_tools_enabled', False)  # Default disable MCP
            strands_tools_enabled = tool_config.get('strands_tools_enabled', True)

            # Get tools if enabled
            if tools_enabled:
                try:
                    # Use tool provider with native Strands mixed tool support
                    base_tools, mcp_clients = tool_provider.get_tools_and_contexts({
                        'include_legacy': include_legacy,
                        'mcp_tools_enabled': mcp_tools_enabled,
                        'strands_tools_enabled': strands_tools_enabled
                    })
                    
                    if mcp_tools_enabled and mcp_clients:
                        logger.info(f"[AgentProvider] Using MCP tools with {len(mcp_clients)} clients")
                        # Use MCP context management
                        async for event_data in self._generate_with_mcp_context(
                            prompt, base_tools, mcp_clients, model, history_messages
                        ):
                            yield event_data
                    else:
                        # No MCP tools, direct Agent creation
                        agent = Agent(
                            tools=base_tools,
                            system_prompt=self.system_prompt,
                            model=model,
                            messages=history_messages
                        )
                        logger.info(f"[AgentProvider] Initialized Strands Agent with {len(base_tools)} tools")
                        
                        async for event_data in self._process_events(agent, prompt):
                            yield event_data
                    
                except Exception as e:
                    logger.error(f"[AgentProvider] Error loading tools: {str(e)}", exc_info=True)
                    # Fallback to no tools
                    agent = Agent(
                        system_prompt=self.system_prompt, 
                        model=model,
                        messages=history_messages
                    )
                    logger.warning(f"[AgentProvider] Falling back to agent without tools")
                    
                    async for event_data in self._process_events(agent, prompt):
                        yield event_data
            else:
                # Tools disabled
                agent = Agent(
                    system_prompt=self.system_prompt, 
                    model=model,
                    messages=history_messages
                )
                logger.info(f"[AgentProvider] Initialized Strands Agent without tools")
                
                async for event_data in self._process_events(agent, prompt):
                    yield event_data
            
        except Exception as e:
            logger.error(f"[AgentProvider] Error during content generation: {str(e)}", exc_info=True)
            raise

    async def get_available_tools(self) -> Dict[str, List[Dict]]:
        """Get information about available tools"""
        try:
            tools_info = tool_provider.list_tools()
            
            # Group by type
            legacy_tools = [t for t in tools_info if t['type'] == 'legacy']
            strands_tools = [t for t in tools_info if t['type'] == 'strands']
            mcp_tools = [t for t in tools_info if t['type'] == 'mcp_server']
            
            return {
                'legacy': legacy_tools,
                'strands': strands_tools,
                'mcp': mcp_tools
            }
        except Exception as e:
            logger.error(f"[AgentProvider] Error getting available tools: {str(e)}")
            return {'legacy': [], 'strands': [], 'mcp': []}

    def enable_tool(self, tool_name: str):
        """Enable a specific tool (placeholder for future implementation)"""
        logger.info(f"[AgentProvider] Enable tool requested: {tool_name}")

    def disable_tool(self, tool_name: str):
        """Disable a specific tool (placeholder for future implementation)"""
        logger.info(f"[AgentProvider] Disable tool requested: {tool_name}")

    async def reload_tools(self):
        """Reload all tools"""
        await tool_provider.reload_tools()
