# Copyright iX.
# SPDX-License-Identifier: MIT-0
from typing import Dict, AsyncIterator, Any, List
from core.logger import logger
from core.service import BaseService
from core.session.models import Session
from genai.agents.agent_provider import AgentProvider


class AgentService(BaseService):
    """Strands Agent service implementation with streaming capabilities"""
    
    def __init__(self, module_name: str):
        """Initialize Agent service
        
        Args:
            module_name: Name of the module using this service
        """
        super().__init__(module_name)
        self._agent_providers: Dict[str, AgentProvider] = {}
    
    async def _get_agent_provider(self, model_id, system_prompt: str):
        """Get or initialize AgentProvider
        
        Args:
            model_id: ID of the model to get provider for
            system_prompt: System prompt for the agent

        Returns:
            AgentProvider instance
        """
        # Use cached provider if available
        if model_id in self._agent_providers:
            logger.debug(f"[AgentService] Using cached provider for model {model_id}")
            return self._agent_providers[model_id]

        else:
            try:
                # Create provider
                provider = AgentProvider(
                    model_id=model_id,
                    system_prompt=system_prompt
                )                
                logger.info(f"[AgentService] Initialized AgentProvider with model {model_id}")
                # Cache provider
                self._agent_providers[model_id] = provider

                return provider

            except Exception as e:
                logger.error(f"[AgentService] Failed to initialize AgentProvider: {str(e)}")
                self._agent_provider = None

    async def gen_text_stream(self, session: Session, prompt: str, system_prompt: str) -> AsyncIterator[Dict]:
        """
        Generate text with streaming response and session context
        
        Args:
            session: User session
            prompt: The user prompt
            system_prompt: System prompt for the agent
            
        Returns:
            AsyncIterator yielding dictionaries
        """
        if not prompt:
            yield {"text": "Please provide a user prompt."}

        try:
            # Get model_id with fallback to module default
            model_id = await self.get_session_model(session)

            # Get provider instance
            provider = await self._get_agent_provider(model_id, system_prompt)

            # Get module configuration for tool filtering
            from core.module_config import module_config
            config = module_config.get_module_config(self.module_name)
            enabled_tools = config.get('enabled_tools', []) if config else []
            
            # Configure tools using Universal Tool Manager
            tool_config = {
                'enabled': True,
                'include_legacy': True,
                'include_mcp': True,  # Enable MCP tools
                'tool_filter': enabled_tools if enabled_tools else None  # Use database config or all tools
            }
            
            logger.debug(f"[AgentService] Using tool filter from database: {enabled_tools}")

            # Track response state
            accumulated_text = []
            accumulated_files = []
            response_metadata = {}

            async for chunk in provider.generate_stream(prompt, tool_config):
                if not isinstance(chunk, dict):
                    logger.warning(f"[AgentService] Unexpected chunk type: {type(chunk)}")
                    continue

                if content := chunk.get('content', {}):
                    # Handle text
                    if text := content.get('text'):
                        yield {'text': text}
                        accumulated_text.append(text)
                    # Handle files
                    elif file_path := content.get('file_path'):
                        yield {'file_path': file_path}
                        accumulated_files.append(file_path)

                # Handle tool use events
                if tool_use := chunk.get('tool_use'):
                    logger.debug(f"[AgentService] Tool use: {tool_use}")
                    # You can yield tool use information if needed
                    # yield {'tool_use': tool_use}

                # Only update metadata if it exists
                if metadata := chunk.get('metadata'):
                    response_metadata.update(metadata)

        except Exception as e:
            logger.error(f"[AgentService] Failed to generate text stream: {str(e)}", exc_info=True)
            yield {"text": "I apologize, but I encountered a error. Please try again later."}
