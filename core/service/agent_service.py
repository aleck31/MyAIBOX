# Copyright iX.
# SPDX-License-Identifier: MIT-0
from typing import Dict, AsyncIterator, Any, List
from core.logger import logger
from core.service import BaseService
from core.session.models import Session
from genai.agents.strands_agent import StrandsAgentProvider


class AgentService(BaseService):
    """Strands Agent service implementation with streaming capabilities"""
    
    def __init__(self, module_name: str):
        """Initialize Agent service
        
        Args:
            module_name: Name of the module using this service
        """
        super().__init__(module_name)
        self._agent_providers: Dict[str, StrandsAgentProvider] = {}
    
    async def _get_agent_provider(self, model_id, system_prompt: str):
        """Get or initialize StrandsAgentProvider
        
        Args:
            model_id: ID of the model to get provider for
            system_prompt: System prompt for the agent

        Returns:
            StrandsAgentProvider instance
        """
        # Use cached provider if available
        if model_id in self._agent_providers:
            logger.debug(f"[AgentService] Using cached provider for model {model_id}")
            return self._agent_providers[model_id]

        else:
            try:
                # Create provider
                provider = StrandsAgentProvider(
                    model_id=model_id,
                    system_prompt=system_prompt
                )                
                logger.info(f"[AgentService] Initialized StrandsAgentProvider with model {model_id}")
                # Cache provider
                self._agent_providers[model_id] = provider
            except Exception as e:
                logger.error(f"[AgentService] Failed to initialize StrandsAgentProvider: {str(e)}")
                self._agent_provider = None
        
        return provider

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
            yield "Please provide a user prompt."

        try:
            # Get model_id with fallback to module default
            model_id = await self.get_session_model(session)

            # Get provider instance
            provider = await self._get_agent_provider(model_id, system_prompt)

            # Track response state
            accumulated_text = []
            accumulated_files = []
            response_metadata = {}

            async for chunk in provider.generate_stream(prompt, mcp_server="exa-server"):
                if not isinstance(chunk, dict):
                    logger.warning(f"[ChatService] Unexpected chunk type: {type(chunk)}")
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

                # Only update metadata if it exists
                if metadata := chunk.get('metadata'):
                    response_metadata.update(metadata)

        except Exception as e:
            logger.error(f"[AgentService] Failed to generate text stream: {str(e)}", exc_info=True)
            yield {"text": "I apologize, but I encountered a error. Please try again later."}
