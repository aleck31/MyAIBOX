from typing import Dict, List, Optional
from datetime import datetime
from common.logger import setup_logger
from core.session import Session, SessionStore
from core.module_config import module_config
from genai.models.model_manager import model_manager
from genai.models import LLMParameters, GenImageParameters
from genai.models.providers import LLMAPIProvider, LLMProviderError, create_model_provider 
from genai.models.providers.bedrock_invoke import BedrockInvoke, create_creative_provider

logger = setup_logger('service')


class BaseService:
    """Base service with common functionality"""

    def __init__(
        self,
        module_name: str,
        cache_ttl: int = 600  # 10 minutes default TTL
    ):
        """Initialize base service without Foundation Model params

        Args:
            module_name: Name of the module using this service
            cache_ttl: Time in seconds to keep sessions in cache (default 10 min)
        """
        self.module_name = module_name
        self.session_store = SessionStore.get_instance()
        self._model_providers: Dict[str, LLMAPIProvider] = {}
        self._creative_providers: Dict[str, BedrockInvoke] = {}
        self._session_cache: Dict[str, tuple[Session, float]] = {}
        self.cache_ttl = cache_ttl
        self.model_id = None

    async def get_or_create_session(
        self,
        user_name: str,
        module_name: str,
        session_name: Optional[str] = None,
        bypass_cache: bool = False
    ) -> Session:
        """Get latest existing session or create new one
        
        Args:
            user_name: User to get/create session for
            module_name: Module name for the session
            session_name: Optional custom session name
            bypass_cache: Whether to bypass cache lookup
            
        Returns:
            Session: Active session for user/module
        """
        cache_key = f"{user_name}:{module_name}"
        
        try:
            # Try cache first unless bypassed
            if not bypass_cache:
                if cached_session := self._session_cache.get(cache_key):
                    session, expiry = cached_session
                    if datetime.now().timestamp() < expiry:
                        return session
                    # Clear expired cache entry
                    del self._session_cache[cache_key]
            
            # Get most recent session from store
            if sessions := await self.session_store.list_sessions(
                user_name=user_name,
                module_name=module_name
            ):
                session = sessions[0]  # Most recent session
            else:
                # Create new session
                name = session_name or f"{module_name.title()} session for {user_name}"
                session = await self.session_store.create_session(
                    user_name=user_name,
                    module_name=module_name,
                    session_name=name
                )
            
            # Update cache with new session
            self._session_cache[cache_key] = (
                session,
                datetime.now().timestamp() + self.cache_ttl
            )
            
            return session

        except Exception as e:
            logger.error(f"[BaseService] Failed to get/create session for {user_name}: {str(e)}")
            raise

    async def get_session_model(self, session: Session) -> str:
        """Get model ID from session or module defaults
        
        Args:
            session: Session to get model for
            
        Returns:
            str: Model ID (guaranteed to return a valid model ID)
            
        Notes:
            - Checks session metadata first
            - Falls back to module config defaults
            - Updates session if default model found
        """
        try:
            # Return existing model_id if set
            if self.model_id:
                logger.debug(f"[BaseService] Get cached model id: {self.model_id}")
                return self.model_id
            elif model_id := session.metadata.model_id:
                logger.debug(f"[BaseService] Get session model id: {model_id}")
                self.model_id = model_id
                return self.model_id
            # Falls back to module config default model
            else:
                model_id = module_config.get_default_model(session.metadata.module_name)
                self.model_id = model_id
                logger.debug(f"[BaseService] Falls back to default model: {model_id}")
                return self.model_id

        except Exception as e:
            logger.error(f"[BaseService] Failed to get model for session {session.session_id}: {str(e)}")
            raise ValueError(f"Unable to get any model ID for session: {str(e)}")

    async def update_session_model(self, session: Session, model_id: str) -> None:
        """Update model ID in session metadata
        
        Args:
            session: Session to update
            model_id: New model ID to set
        """
        try:
            if self.model_id != model_id:
                self.model_id = model_id
                session.metadata.model_id = model_id
                await self.session_store.save_session(session)
                logger.debug(f"[BaseService] Updated model to {model_id} in session {session.session_id}")
        except Exception as e:
            logger.error(f"[BaseService] Failed to update session model: {str(e)}")
            raise

    def _get_model_provider(self, model_id: str, llm_params: Optional[LLMParameters] = None) -> LLMAPIProvider:
        """Get or create Foundation model provider
        
        Args:
            model_id: ID of the model to get provider for
            llm_params: Optional inference parameters to override defaults
            
        Returns:
            LLMAPIProvider: Provider for text generation
        """
        try:
            # Use cached provider if available and no custom params
            if model_id in self._model_providers and not llm_params:
                logger.debug(f"[BaseService] Using cached provider for model {model_id}")
                return self._model_providers[model_id]

            # Get model info and validate it's a text model
            if model := model_manager.get_model_by_id(model_id):
                if model.category == 'image':
                    raise ValueError(f"Model {model_id} is an image model, use _get_creative_provider instead")
                logger.debug(f"[BaseService] Found text model: {model.name} ({model.api_provider})")
            else:
                raise ValueError(f"Model not found: {model_id}")

            # Get default params if not provided
            if not llm_params:
                params = module_config.get_inference_params(self.module_name) or {}
                
                # Ensure proper type conversion for numeric parameters
                if 'max_tokens' in params:
                    params['max_tokens'] = int(params['max_tokens'])
                if 'temperature' in params:
                    params['temperature'] = float(params['temperature'])
                if 'top_p' in params:
                    params['top_p'] = float(params['top_p'])
                if 'top_k' in params:
                    params['top_k'] = int(params['top_k'])
                
                llm_params = LLMParameters(**params)

            # Get enabled tools
            enabled_tools = module_config.get_enabled_tools(self.module_name)

            # Create text model provider
            provider = create_model_provider(
                model.api_provider,
                model_id,
                llm_params,
                enabled_tools
            )
            
            # Cache provider if using default params
            if not llm_params:
                self._model_providers[model_id] = provider

            logger.debug(f"[BaseService] Created text provider for model {model_id}")
            return provider

        except LLMProviderError as e:
            logger.error(f"[BaseService] Provider error for text model {model_id}: {e.error_code}")
            raise
        except Exception as e:
            logger.error(f"[BaseService] Failed to get text provider for {model_id}: {str(e)}")
            raise

    def _get_creative_provider(self, model_id: str, gen_params: Optional[GenImageParameters] = None) -> BedrockInvoke:
        """Get or create creative content generation provider
        
        Args:
            model_id: ID of the creative model (image/video/audio)
            gen_params: Optional generation parameters to override defaults
            
        Returns:
            LLMAPIProvider: Provider for creative content generation
        """
        try:
            # Use cached provider if available and no custom params
            if model_id in self._creative_providers and not gen_params:
                logger.debug(f"[BaseService] Using cached creative provider for model {model_id}")
                return self._creative_providers[model_id]

            # Get model info and validate it's a creative model
            if model := model_manager.get_model_by_id(model_id):
                if model.category != 'image':
                    raise ValueError(f"Model {model_id} is not a creative model, use _get_text_provider instead")
                logger.debug(f"[BaseService] Found creative model: {model.name} ({model.api_provider})")
            else:
                raise ValueError(f"Model not found: {model_id}")

            # Get default params if not provided
            if not gen_params:
                params = module_config.get_inference_params(self.module_name) or {}
                
                # Ensure proper type conversion for numeric parameters
                if 'height' in params:
                    params['height'] = int(params['height'])
                if 'width' in params:
                    params['width'] = int(params['width'])
                if 'img_number' in params:
                    params['img_number'] = int(params['img_number'])
                if 'cfg_scale' in params:
                    params['cfg_scale'] = float(params['cfg_scale'])
                
                gen_params = GenImageParameters(**params)

            # Create creative provider
            provider = create_creative_provider(
                model.api_provider,
                model_id,
                gen_params,
                region=model.region or None
            )

            # Cache provider if using default params
            if not gen_params:
                self._creative_providers[model_id] = provider

            logger.debug(f"[BaseService] Created creative provider for model {model_id}")
            return provider

        except LLMProviderError as e:
            logger.error(f"[BaseService] Provider error for creative model {model_id}: {e.error_code}")
            raise
        except Exception as e:
            logger.error(f"[BaseService] Failed to get creative provider for {model_id}: {str(e)}")
            raise

    async def load_session_history(
        self,
        session: Session,
        max_messages: int = 24
    ) -> List[Dict[str, str]]:
        """Load formatted chat history from session"""
        try:
            if not session.history:
                return []
                
            messages = []
            # Process only the most recent messages up to max_number
            for msg in session.history[-max_messages:]:
                content = msg['content']
                
                if isinstance(content, dict):
                    # Handle text content
                    if text := content.get('text'):
                        messages.append({
                            "role": msg['role'],
                            "content": text
                        })
                    # Handle file content separately
                    if files := content.get('files'):
                        messages.append({
                            "role": msg['role'],
                            "content": files
                        })
                else:
                    # Handle legacy string content
                    messages.append({
                        "role": msg['role'],
                        "content": content
                    })
                    
            return messages
            
        except Exception as e:
            logger.error(f"[BaseService] Failed to load history from session {session.session_id}: {str(e)}")
            return []  # Return empty history on error
