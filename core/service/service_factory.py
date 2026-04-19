from .chat_service import ChatService
from .gen_service import GenService
from .draw_service import DrawService
from .agent_service import AgentService


class ServiceFactory:
    """Factory for creating service instances"""

    @classmethod
    def create_gen_service(cls, module_name: str) -> GenService:
        return GenService(module_name=module_name)

    @classmethod
    def create_chat_service(cls, module_name: str) -> ChatService:
        return ChatService(module_name=module_name)

    @classmethod
    def create_draw_service(cls, module_name: str = 'draw') -> DrawService:
        return DrawService(module_name=module_name)

    @classmethod
    def create_agent_service(cls, module_name: str = 'assistant') -> AgentService:
        return AgentService(module_name=module_name)
