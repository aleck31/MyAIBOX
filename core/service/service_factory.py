from .chat_service import ChatService
from .gen_service import GenService
from .draw_service import DrawService
from .agent_service import AgentService
from . import logger


class ServiceFactory:
    """Factory for creating service instances"""

    @classmethod
    def create_gen_service(cls, module_name: str) -> GenService:
        """Create general content generation service
        
        Args:
            module_name: Name of the module requesting service
            
        Returns:
            GenService: Configured service instance
        """
        try:
            logger.debug(f"Creating GenService for {module_name}")
            return GenService(module_name=module_name)
        except Exception as e:
            logger.error(f"Failed to create GenService: {str(e)}")
            raise

    @classmethod
    def create_chat_service(cls, module_name: str) -> ChatService:
        """Create chat service with streaming capabilities
        
        Args:
            module_name: Name of the module requesting service
            
        Returns:
            ChatService: Configured service instance
        """
        try:
            logger.debug(f"Creating ChatService for {module_name}")
            return ChatService(module_name=module_name)
        except Exception as e:
            logger.error(f"Failed to create ChatService: {str(e)}")
            raise

    @classmethod
    def create_draw_service(cls, module_name: str = 'draw') -> DrawService:
        """Create image generation service
        
        Args:
            module_name: Name of the module requesting service (defaults to 'draw')
            
        Returns:
            DrawService: Configured service instance
        """
        try:
            logger.debug(f"Creating DrawService for {module_name}")
            return DrawService(module_name=module_name)
        except Exception as e:
            logger.error(f"Failed to create DrawService: {str(e)}")
            raise

    @classmethod
    def create_agent_service(cls, module_name: str = 'assistant') -> AgentService:
        """Create Strands agent service
        
        Args:
            module_name: Name of the module requesting service (defaults to 'assistant')
            
        Returns:
            AgentService: Configured service instance
        """
        try:
            logger.debug(f"Creating AgentService for {module_name}")
            return AgentService(module_name=module_name)
        except Exception as e:
            logger.error(f"Failed to create AgentService: {str(e)}")
            raise
