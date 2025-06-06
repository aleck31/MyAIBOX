# Copyright iX.
# SPDX-License-Identifier: MIT-0
import asyncio
import gradio as gr
from typing import Dict, Union, AsyncIterator 
from core.logger import logger
from modules import BaseHandler
from core.service.service_factory import ServiceFactory
from genai.models.model_manager import model_manager
from .prompts import SYSTEM_PROMPT


class DeepSearchHandlers(BaseHandler):
    """Handlers for Deep Search module using Strands Agents SDK"""
    
    # Module name for the handler
    _module_name: str = "deepsearch"
    
    # Service type
    _service_type: str = "agent"
    
    @classmethod
    def get_available_models(cls):
        """Get list of available models with id and names"""
        try:
            # Filter for models with tool use capability
            if models := model_manager.get_models(filter={'tool_use': True}):
                logger.debug(f"[{cls.__name__}] Get {len(models)} available models")
                return [(f"{m.name}, {m.api_provider}", m.model_id) for m in models]
            else:
                logger.warning(f"[{cls.__name__}] No matching models found.")
                return []
        except Exception as e:
            logger.error(f"[{cls.__name__}] Failed to fetch models: {str(e)}", exc_info=True)
            return []
    
    @classmethod
    async def _get_service(cls):
        """Get or initialize service for Deep Search module"""
        if cls._service is None:
            logger.info(f"[{cls.__name__}] Initializing DeepSearch service")
            cls._service = ServiceFactory.create_agent_service(cls._module_name)
        return cls._service

    @classmethod
    async def search(cls, query: Union[str, Dict], request: gr.Request) -> AsyncIterator[str]:
        """
        Perform a deep search using Strands Agents
        
        Args:
            query: The search query (can be a string or a dictionary)
            request: Gradio request with session data
            
        Returns:
            AsyncIterator yielding search results as they become available
        """
        if not query:
            yield "Please provide a search query."

        try:
            # Initialize service and session
            service, session = await cls._init_session(request)

            # Extract text from query if it's a dict (from MultimodalTextbox)
            query_text = query.get('text', '') if isinstance(query, dict) else query

            # Generate response with streaming
            response_buffer = ""

            # Perform search using the service
            async for chunk in service.gen_text_stream(
                session=session,
                prompt=query_text,
                system_prompt=SYSTEM_PROMPT
            ):
                # Process structured chunks from AgentService
                if text := chunk.get('text'):
                    # Add text content to response buffer
                    response_buffer += text

                # Yield current state of both buffers
                yield response_buffer.strip()
                await asyncio.sleep(0)  # Add sleep for Gradio UI streaming            

        except Exception as e:
            error_type = type(e).__name__
            error_message = str(e)
            logger.error(f"[{cls.__name__}] Failed to perform search: {str(e)}", exc_info=True)
            gr.Error(title=error_type, message=error_message, duration=9)
