"""Service for creative content generation"""
from typing import Dict, Optional
from core.logger import logger
from core.session import Session
from genai.models.api_providers import LLMMessage, LLMProviderError
from . import BaseService


class CreativeService(BaseService):
    """Service for creative content (image, video) generation"""
    
    def __init__(
        self,
        module_name: str,
        cache_ttl: int = 600  # 10 minutes default TTL
    ):
        """Initialize Creative Service

        Args:
            module_name: Name of the module using this service
            cache_ttl: Cache time-to-live in seconds
        """
        super().__init__(module_name=module_name, cache_ttl=cache_ttl)

    def _prepare_message(self, content: Dict[str, str]) -> LLMMessage:
        """Create standardized message format"""
        return LLMMessage(
            role="user",
            content=content if isinstance(content, dict) else {"text": str(content)}
        )

    async def generate_video_stateless(
        self,
        content: Dict[str, str],
        system_prompt: Optional[str] = None,
        option_params: Optional[Dict[str, float]] = None
    ) -> str:
        """Generate video using the configured LLM without session context
        
        Args:
            content: Dictionary containing text and optional image
            system_prompt: Optional system prompt for one-off generation
            option_params: Optional parameters for LLM generation
            
        Returns:
            str: Generated video URL or path
        """
        try:
            # Always use default model for stateless operations
            provider = self._get_model_provider(self.model_id)
            
            logger.debug(f"[CreativeService] Content for stateless generation: {content}")
            
            # Create standardized message
            messages = [self._prepare_message(content)]

            # Generate response
            response = await provider.generate_content(
                messages=messages,
                system_prompt=system_prompt,
                **(option_params or {})
            )
            
            if not response.content:
                raise ValueError("Empty response from LLM Provider")
                
            return response.content.get('video_url', '')

        except LLMProviderError as e:
            logger.error(f"[CreativeService] Failed to generate video stateless: {e.error_code}")
            # Return user-friendly message from provider
            return f"I apologize, {e.message}"

    async def generate_video(
        self,
        session: Session,
        content: Dict[str, str],
        option_params: Optional[Dict[str, float]] = None
    ) -> str:
        """Generate video using the configured LLM with session context
        
        Args:
            session: Session for context management
            content: Dictionary containing text and optional image
            option_params: Optional parameters for LLM generation
            
        Returns:
            str: Generated video URL or path
        """
        try:
            # Get model_id with fallback to module default
            model_id = await self.get_session_model(session)

            # Get LLM provider
            provider = self._get_model_provider(model_id)
            
            logger.debug(f"[CreativeService] Content for session {session.session_id}: {content}")
            
            # Create message with multimodal content support
            message = self._prepare_message(content)

            # Generate response
            response = await provider.generate_content(
                messages=[message],
                system_prompt=session.context.get('system_prompt', ''),
                **(option_params or {})
            )

            if not response.content:
                raise ValueError("Empty response from LLM Provider")
                
            # Add interactions to session
            session.add_interaction({
                "role": "user",
                "content": content
            })
            
            session.add_interaction({
                "role": "assistant",
                "content": response.content,
                "metadata": getattr(response, 'metadata', None)
            })
            
            # Update session
            await self.session_store.save_session(session)

            return response.content.get('video_url', '')

        except LLMProviderError as e:
            logger.error(f"[CreativeService] Failed to generate video in session {session.session_id}: {e.error_code}")
            # Return user-friendly message from provider
            return f"I apologize, {e.message}"
