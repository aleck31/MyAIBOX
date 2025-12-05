# Copyright iX.
# SPDX-License-Identifier: MIT-0
from typing import Dict, AsyncIterator, Any, List, Optional
from core.service import BaseService
from core.session.models import Session
from genai.agents.provider import AgentProvider
from . import logger


class AgentService(BaseService):
    """Strands Agent service implementation with streaming capabilities"""
    
    def __init__(self, module_name: str):
        """Initialize Agent service
        
        Args:
            module_name: Name of the module using this service
        """
        super().__init__(module_name)
        self._agent_providers: Dict[str, AgentProvider] = {}
    
    def _convert_to_strands_format(self, ui_history: List[Dict]) -> List:
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
                raise  # Re-raise instead of returning None

    def _get_default_tool_config(self) -> Dict[str, Any]:
        """Get default tool configuration for the service
        
        Note: No longer reads from database - modules should pass their own legacy_tools
        
        Returns:
            Default tool configuration dictionary
        """
        tool_config = {
            'enabled': True,
            'legacy_tools': [],  # Empty by default - modules should specify their tools
            'mcp_tools_enabled': False,  # Default disable MCP for performance
            'strands_tools_enabled': True,
        }
        
        logger.debug(f"[AgentService] Using default tool config (no legacy tools)")
        return tool_config

    async def _generate_stream_async(
        self, 
        session: Session, 
        prompt: str, 
        system_prompt: str, 
        history: Optional[List[Dict]] = None,
        tool_config: Optional[Dict[str, Any]] = None
    ) -> AsyncIterator[Dict]:
        """Internal method for streaming generation with common logic
        
        Args:
            session: User session
            prompt: Current user prompt
            system_prompt: System prompt for the agent
            history: Optional list of previous messages in UI format
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

            # Convert UI history to Strands format if provided
            strands_history = None
            if history:
                strands_history = self._convert_to_strands_format(history)

            # Use provided tool config or get default
            if tool_config is None:
                tool_config = self._get_default_tool_config()
            else:
                logger.debug(f"Using provided tool config: {tool_config}")

            # Stream standardized responses
            async for chunk in provider.generate_stream(prompt, strands_history, tool_config):
                if not isinstance(chunk, dict):
                    logger.warning(f"Unexpected chunk type: {type(chunk)}")
                    continue

                # Direct pass-through of standardized format
                yield chunk

        except Exception as e:
            logger.error(f"Error in streaming generation: {str(e)}", exc_info=True)
            yield {"text": f"I apologize, but I encountered an error while processing your request: {str(e)}"}

    async def streaming_reply_with_history(
        self, 
        session: Session, 
        prompt: str, 
        system_prompt: str, 
        history: List[Dict],
        tool_config: Dict[str, Any]
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
        # Track response state for saving to session
        accumulated_text = []
        accumulated_files = []
        response_metadata = {}
        
        try:
            async for chunk in self._generate_stream_async(
                session=session,
                prompt=prompt,
                system_prompt=system_prompt,
                history=history,
                tool_config=tool_config
            ):
                # Collect response content for session saving
                if text := chunk.get('text'):
                    accumulated_text.append(text)
                
                if files := chunk.get('files'):
                    if isinstance(files, list):
                        accumulated_files.extend(files)
                    else:
                        accumulated_files.append(files)
                
                if metadata := chunk.get('metadata'):
                    response_metadata.update(metadata)
                
                # Yield chunk to caller
                yield chunk

            # Save chat history after successful streaming (similar to ChatService)
            if accumulated_text or accumulated_files:
                from datetime import datetime
                
                # Create user message
                user_message = {
                    "role": "user",
                    "content": {"text": prompt},
                    "context": {
                        'local_time': datetime.now().astimezone().isoformat(),
                        'user_name': session.user_name
                    }
                }
                
                # Create assistant message
                assistant_message = {
                    "role": "assistant",
                    "content": {
                        "text": ''.join(accumulated_text),
                        "files": accumulated_files
                    },
                    "metadata": response_metadata if response_metadata else None
                }
                
                # Add both messages to session history
                session.add_interaction(user_message)
                session.add_interaction(assistant_message)
                
                # Persist to session store
                await self.session_store.save_session(session)
                logger.debug(f"Saved chat interaction to session {session.session_id}")
                
        except Exception as e:
            logger.error(f"Error in streaming reply with history: {str(e)}", exc_info=True)
            yield {"text": f"I apologize, but I encountered an error while processing your request: {str(e)}"}

    async def gen_text_stream(
        self, 
        session: Session, 
        prompt: str, 
        system_prompt: str, 
        tool_config: Optional[Dict[str, Any]] = None
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
        async for chunk in self._generate_stream_async(
            session=session,
            prompt=prompt,
            system_prompt=system_prompt,
            history=None,  # No history for single-turn
            tool_config=tool_config
        ):
            yield chunk

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
