# Copyright iX.
# SPDX-License-Identifier: MIT-0
from typing import Dict, AsyncIterator, Any, List
from core.logger import logger
from core.service import BaseService
from core.session.models import Session
from genai.agents.provider import AgentProvider


class AgentService(BaseService):
    """Strands Agent service implementation with streaming capabilities"""
    
    def __init__(self, module_name: str):
        """Initialize Agent service
        
        Args:
            module_name: Name of the module using this service
        """
        super().__init__(module_name)
        self._agent_providers: Dict[str, AgentProvider] = {}
    
    def _convert_ui_to_strands_format(self, ui_history: List[Dict]) -> List:
        """Convert UI history messages to Strands Message format
        
        Args:
            ui_history: List of message dicts with 'role' and 'content' keys from UI
            
        Returns:
            List of Strands Message objects
        """
        if not ui_history:
            return []
            
        try:
            from strands.types.content import Message
            strands_messages = []
            
            for msg in ui_history:
                if isinstance(msg, dict) and 'role' in msg and 'content' in msg:
                    # Handle different content formats
                    content = msg['content']
                    if isinstance(content, dict):
                        # Extract text from dict format
                        content = content.get('text', str(content))
                    elif isinstance(content, (list, tuple)):
                        # Convert list/tuple to text
                        content = ' '.join(str(item) for item in content)
                    
                    # Convert to correct Bedrock format
                    strands_msg = Message({
                        'role': msg['role'],
                        'content': [
                            {
                                'text': str(content)
                            }
                        ]
                    })
                    strands_messages.append(strands_msg)
                    
            logger.debug(f"[AgentService] Converted {len(ui_history)} UI messages to Strands format")
            return strands_messages
            
        except Exception as e:
            logger.error(f"[AgentService] Error converting UI messages to Strands format: {str(e)}")
            return []
    
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

    async def streaming_reply_with_history(
        self, 
        session: Session, 
        prompt: str, 
        system_prompt: str, 
        history: List[Dict],
        tool_config: Dict[str, Any] = None
    ) -> AsyncIterator[Dict]:
        """
        Generate streaming response with conversation history (multi-turn)
        
        Args:
            session: User session
            prompt: Current user prompt
            system_prompt: System prompt for the agent
            history: List of previous messages in UI format
                - Format: [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
            tool_config: Optional tool configuration override
            
        Returns:
            AsyncIterator yielding standardized agent response dictionaries
        """
        if not prompt:
            yield {"text": "Please provide a user prompt."}
            return

        try:
            # Get model_id with fallback to module default
            model_id = await self.get_session_model(session)

            # Get provider instance
            provider = await self._get_agent_provider(model_id, system_prompt)

            # Convert UI history to Strands format in Service layer
            strands_history = self._convert_ui_to_strands_format(history) if history else []

            # Configure tools - use provided config or default
            if tool_config is None:
                # Get module configuration for tool filtering
                from core.module_config import module_config
                config = module_config.get_module_config(self.module_name)
                enabled_tools = config.get('enabled_tools', []) if config else []
                
                tool_config = {
                    'enabled': True,
                    'include_legacy': True,
                    'include_mcp': True,
                    'include_strands': True,
                    'tool_filter': enabled_tools if enabled_tools else None
                }
                
                logger.debug(f"[AgentService] Using tool filter from database: {enabled_tools}")
            else:
                logger.debug(f"[AgentService] Using provided tool config: {tool_config}")

            # Stream standardized responses with converted history
            async for chunk in provider.generate_stream(prompt, strands_history, tool_config):
                if not isinstance(chunk, dict):
                    logger.warning(f"[AgentService] Unexpected chunk type: {type(chunk)}")
                    continue

                # Direct pass-through of standardized format
                yield chunk

        except Exception as e:
            logger.error(f"[AgentService] Error in streaming_reply_with_history: {str(e)}", exc_info=True)
            yield {"text": f"I apologize, but I encountered an error while processing your request: {str(e)}"}

    async def gen_text_stream(
        self, 
        session: Session, 
        prompt: str, 
        system_prompt: str, 
        tool_config: Dict[str, Any] = None
    ) -> AsyncIterator[Dict]:
        """
        Generate text with streaming response (single-turn)
        
        Args:
            session: User session
            prompt: The user prompt
            system_prompt: System prompt for the agent
            tool_config: Optional tool configuration override
            
        Returns:
            AsyncIterator yielding standardized agent response dictionaries
        """
        if not prompt:
            yield {"text": "Please provide a user prompt."}
            return

        try:
            # Get model_id with fallback to module default
            model_id = await self.get_session_model(session)

            # Get provider instance
            provider = await self._get_agent_provider(model_id, system_prompt)

            # Configure tools - use provided config or default
            if tool_config is None:
                # Get module configuration for tool filtering
                from core.module_config import module_config
                config = module_config.get_module_config(self.module_name)
                enabled_tools = config.get('enabled_tools', []) if config else []
                
                tool_config = {
                    'enabled': True,
                    'include_legacy': True,
                    'include_mcp': True,
                    'include_strands': True,
                    'tool_filter': enabled_tools if enabled_tools else None
                }
                
                logger.debug(f"[AgentService] Using tool filter from database: {enabled_tools}")
            else:
                logger.debug(f"[AgentService] Using provided tool config: {tool_config}")

            # Stream standardized responses without history (single-turn)
            async for chunk in provider.generate_stream(prompt, None, tool_config):
                if not isinstance(chunk, dict):
                    logger.warning(f"[AgentService] Unexpected chunk type: {type(chunk)}")
                    continue

                # Direct pass-through of standardized format
                yield chunk

        except Exception as e:
            logger.error(f"[AgentService] Error in gen_text_stream: {str(e)}", exc_info=True)
            yield {"text": f"I apologize, but I encountered an error while processing your request: {str(e)}"}

    async def clear_history(self, session: Session) -> None:
        """Clear chat history for a session
        
        Args:
            session: Active chat session to clear history for
            
        Note:
            - Clears the history list
            - Updates timestamp
            - Persists changes to session store
        """
        session.history = []  # Clear message history
        await self.session_store.save_session(session)
        logger.debug(f"[AgentService] Cleared history for session {session.session_id}")
