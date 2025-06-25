# Copyright iX.
# SPDX-License-Identifier: MIT-0
import gradio as gr
from typing import Optional, Union, Dict, List, TypeVar, Generic, Type, cast
from core.logger import logger
from core.service.service_factory import ServiceFactory
from core.service.chat_service import ChatService
from core.service.gen_service import GenService
from core.service.draw_service import DrawService
from core.service.agent_service import AgentService

# Define service type variable
ServiceType = TypeVar('ServiceType', bound=Union[ChatService, DrawService, GenService, AgentService])


class BaseHandler(Generic[ServiceType]):
    """Base handler class with generic service type support"""
    
    # Shared service instances - Subclass needs to override the type
    _service: Optional[ServiceType] = None
    
    # Module name for the handler
    _module_name: str = "base"
    
    @classmethod
    def get_service_class(cls) -> Type[ServiceType]:
        """Get the service class type from generic parameter"""
        # Use getattr to safely access __orig_bases__
        orig_bases = getattr(cls, '__orig_bases__', ())
        if orig_bases:
            for base in orig_bases:
                if hasattr(base, '__origin__') and base.__origin__ is BaseHandler:
                    if hasattr(base, '__args__') and base.__args__:
                        return base.__args__[0]
        
        # If unable to auto-detect, raise error to prompt subclass implementation
        raise NotImplementedError(f"{cls.__name__} must specify service type in BaseHandler[ServiceType]")
    
    @classmethod
    async def _get_service(cls) -> ServiceType:
        """Get or initialize service lazily based on service type"""
        if cls._service is None:
            service_class = cls.get_service_class()
            logger.info(f"[{cls.__name__}] Initializing {service_class.__name__}")
            
            # Create service based on service type using if-elif (match-case has issues with types)
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

            # Use cast to tell type checker this is the correct type
            cls._service = cast(ServiceType, service)

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
    def _normalize_input(cls, ui_input: Union[str, Dict]) -> Dict[str, Union[str, List]]:
        """
        Normalize different input formats into unified dictionary.

        Args:
            ui_input: Raw input from Gradio UI (string or dict)

        Returns:
            Normalized dictionary with text and optional files
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
