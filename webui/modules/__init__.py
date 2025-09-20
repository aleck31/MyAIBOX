# Copyright iX.
# SPDX-License-Identifier: MIT-0
import gradio as gr
from typing import Optional, Union, Dict, Any, TYPE_CHECKING
from core.service.service_factory import ServiceFactory
from common.logger import setup_logger
# Import for type checking only to avoid circular imports
if TYPE_CHECKING:
    from core.service import BaseService

logger = setup_logger('webui')


class BaseHandler:
    """Base handler class with service type support"""
     
    # Module name for the handler
    _module_name: str = "base"

    # Shared service instances
    _service_class = None  # Subclass must override this
    _service: Optional['BaseService'] = None

    @classmethod
    def get_service_class(cls):
        """Get the service class type from class attribute"""
        if cls._service_class is None:
            raise NotImplementedError(f"{cls.__name__} must define _service_class attribute")
        return cls._service_class
    
    @classmethod
    async def _get_service(cls):
        """Get or initialize service lazily based on service type
        
        Returns:
            Service instance with the correct type based on _service_class
        """
        if cls._service is None:
            service_class = cls.get_service_class()
            logger.info(f"[{cls.__name__}] Initializing {service_class.__name__}")
            
            # Import service classes dynamically to avoid circular imports
            from core.service.chat_service import ChatService
            from core.service.gen_service import GenService
            from core.service.draw_service import DrawService
            from core.service.agent_service import AgentService
            
            # Create service based on service type using if-elif
            if service_class is ChatService:
                service = ServiceFactory.create_chat_service(cls._module_name)
            elif service_class is DrawService:
                service = ServiceFactory.create_draw_service(cls._module_name)
            elif service_class is AgentService:
                service = ServiceFactory.create_agent_service(cls._module_name)
            elif service_class is GenService:
                service = ServiceFactory.create_gen_service(cls._module_name)
            else:
                raise ValueError(f"Unknown service type: {service_class}")

            cls._service = service

        # Return service with correct type annotation based on _service_class
        return cls._service

    @classmethod
    async def _init_session(cls, request: gr.Request):
        """Initialize service and session
        
        A helper method to get both service and session in one call,
        reducing code duplication across handler methods.
        
        Args:
            request: Gradio request with session data
            
        Returns:
            Tuple of (service, session)
        """
        service = await cls._get_service()
        if service is None:
            raise RuntimeError(f"Failed to create service for {cls._module_name}")

        # Get authenticated user from FastAPI session
        if user_name := request.session.get('auth_user', {}).get('username'):
            session = await service.get_or_create_session(
                user_name=user_name,
                module_name=cls._module_name
            )
            return service, session
        else:
            logger.warning(f"[{cls.__name__}] No authenticated user for loading model")
            raise RuntimeError(f"Failed to create session - no authenticated user")

    @classmethod
    def _normalize_input(cls, ui_input: Union[str, Dict]) -> Dict[str, Any]:
        """
        Normalize different input formats into unified dictionary.

        Args:
            ui_input: Raw input from Gradio UI (string or dict)

        Returns:
            Normalized dictionary with text (str) and optional files (List[str])
        """
        # for Text-only input
        if isinstance(ui_input, str):
            return {"text": ui_input.strip()}
        # for Dict input with potential files
        return {
            k: v for k, v in {
                "text": ui_input.get("text", "").strip(),
                "files": ui_input.get("files", [])
            }.items() if v  # Remove empty values
        }

    @classmethod
    async def update_model_id(cls, model_id: str, request: gr.Request):
        """Update session model when dropdown selection changes"""
        if request is None:
            logger.warning(f"[{cls.__name__}] No request provided for update_model_id")
            return
        try:
            # Initialize service and session
            service, session = await cls._init_session(request)

            # Update model and log
            logger.debug(f"[{cls.__name__}] Updating session model to: {model_id}")
            if session:
                await service.update_session_model(session, model_id)

        except Exception as e:
            logger.error(f"[{cls.__name__}] Failed updating session model: {str(e)}", exc_info=True)
            
    @classmethod
    async def get_model_id(cls, request: gr.Request):
        """Get selected model id from session"""
        try:
            # Initialize service and session
            service, session = await cls._init_session(request)

            # Get current model id from session
            model_id = await service.get_session_model(session)
            logger.debug(f"[{cls.__name__}] Get model {model_id} from session")
            return model_id

        except Exception as e:
            logger.error(f"[{cls.__name__}] Failed loading selected model: {str(e)}", exc_info=True)
            return None
