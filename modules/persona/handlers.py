import asyncio
import gradio as gr
from typing import List, Dict, AsyncGenerator, Union, Optional, Tuple
from core.logger import logger
from core.service.chat_service import ChatService
from genai.models.model_manager import model_manager
from modules import BaseHandler
from .prompts import PERSONA_ROLES


class ChatbotHandlers(BaseHandler[ChatService]):
    """Handlers for chat functionality with session management."""

    # Module name for the handler
    _module_name: str = "persona"

    # Maximum number of messages to show in UI
    _max_display_messages: int = 24

    @classmethod
    def get_available_models(cls) -> List[Tuple[str, str]]:
        """Get list of available models with id and names."""
        try:
            # Filter for models by output modality
            if models := model_manager.get_models(filter={'output_modality': ['text']}):
                logger.debug(f"[ChatbotHandlers] Get {len(models)} available models")
                return [(f"{m.name}, {m.api_provider}", m.model_id) for m in models]
            else:
                logger.warning("[ChatbotHandlers] No Text modality models available")
                return []

        except Exception as e:
            logger.error(f"[ChatbotHandlers] Failed to fetch models: {e}", exc_info=True)
            return []

    @classmethod
    async def load_history_options(
        cls, request: gr.Request
    ) -> Tuple[List[Dict[str, str]], Optional[str], Optional[str]]:
        """
        Load chat history and configuration for current user.

        Args:
            request: Gradio request with session data

        Returns:
            Tuple containing:
            - List of message dictionaries for gr.Chatbot UI
            - Selected model_id for the dropdown
            - Selected persona role for the radio button
        """
        try:
            # Initialize session
            service, session = await cls._init_session(request)

            history_future = service.load_session_history(
                session=session,
                max_messages=cls._max_display_messages
            )
            model_future = service.get_session_model(session)

            # Get persona role from session context if available
            role_future = service.get_session_role(session)

            latest_history, model_id, persona_role = await asyncio.gather(
                history_future, model_future, role_future
            )

            # Return history, model_id and persona_role
            return latest_history, model_id, persona_role

        except Exception as e:
            logger.error(f"[ChatbotHandlers] Failed to load history: {e}", exc_info=True)
            return [], None, None

    @classmethod
    async def clear_chat_history(
        cls, request: gr.Request
    ) -> None:
        """
        Clear chat history when clear button is clicked.

        Args:
            request: Gradio request with session data
        """
        try:
            # Initialize session
            service, session = await cls._init_session(request)

            # Clear history in session
            await service.clear_history(session)
            logger.debug(f"[ChatbotHandlers] Cleared history for user: {session.user_name}")
            gr.Info(f"Cleared history for session {session.session_name}", duration=3)

        except Exception as e:
            logger.error(f"[ChatbotHandlers] Failed to clear history: {e}", exc_info=True)
            
    @classmethod
    async def undo_last_message(
        cls, request: gr.Request
    ) -> None:
        """
        Remove the last pair of messages (user and assistant) from chat history when undo button is clicked.

        Args:
            request: Gradio request with session data
        """
        try:
            # Initialize session
            service, session = await cls._init_session(request)

            # Check if there are messages to remove
            if len(session.history) >= 2:
                # Remove the last two messages (assistant and user)
                session.history = session.history[:-2]
                # Update session in database
                await service.session_store.save_session(session)
                logger.debug(f"[ChatbotHandlers] Removed last message pair for user: {session.user_name}")
            else:
                # No messages to remove
                gr.Info(f"No messages to undo for this session.", duration=3)
            
        except Exception as e:
            logger.error(f"[ChatbotHandlers] Failed to undo last message: {e}", exc_info=True)

    @classmethod
    async def update_persona_role(cls, chat_style: str, request: gr.Request):
        """Update session persona role when option selection changes"""
        try:
            # Check if request is provided
            if request is None:
                logger.warning(f"[{cls.__name__}] No request provided for persona role update")
                return
                
            # Initialize service and session
            service, session = await cls._init_session(request)

            # Update persona role using service method
            await service.update_session_role(session, chat_style)
            logger.debug(f"[{cls.__name__}] Updated session persona role to: {chat_style}")

        except Exception as e:
            logger.error(f"[{cls.__name__}] Failed updating session persona role: {str(e)}", exc_info=True)
    
    @classmethod
    async def send_message(
        cls,
        ui_input: Union[str, Dict],
        ui_history: List[Dict[str, str]],
        chat_style: str,
        model_id: str,
        request: gr.Request
    ) -> AsyncGenerator[Union[Dict[str, str], gr.ChatMessage, List[gr.ChatMessage]], None]:
        """
        Stream assistant's response to user input.

        Args:
            ui_input: Raw input from Gradio (text string or dict with text/files)
            ui_history: Current chat history (managed by Gradio)
            chat_style: Selected chat style option
            model_id: Selected model identifier
            request: Gradio request with session data

        Yields:
            Either a dict with text/files or a list of ChatMessage objects
        """
        # Input validation
        if not model_id:
            yield {"text": "Please select a model for Chatbot module."}
            return
        # Convert Gradio input to a unified dictionary format
        unified_input = cls._normalize_input(ui_input)
        if not unified_input:
            yield {"text": "Please provide a message or file."}
            return
        logger.debug(f"[ChatbotHandlers] User message from Gradio UI: {ui_input}")

        try:
            # Initialize session
            service, session = await cls._init_session(request)

            # Configure chat style
            style_config = PERSONA_ROLES.get(chat_style) or PERSONA_ROLES['default']
            session.context['system_prompt'] = style_config["prompt"]
            style_params = {k: v for k, v in style_config["options"].items() if v is not None}

            logger.debug(f"[ChatbotHandlers] Processing message: {unified_input}")

            # Stream response
            accumulated_text = ""
            accumulated_thinking = ""
            thinking_msg = None

            async for chunk in service.streaming_reply(
                session=session,
                ui_input=unified_input,
                ui_history=ui_history,
                style_params=style_params
            ):
                # Handle streaming chunks for immediate UI updates
                if isinstance(chunk, dict):
                    # Handle thinking (for thinking process)
                    if thinking := chunk.get('thinking'):
                        accumulated_thinking += thinking
                        thinking_msg = gr.ChatMessage(
                            content=accumulated_thinking,
                            metadata={"title": "💭 Thinking Process"}
                        )
                        yield thinking_msg

                    # Handle regular text content
                    if text := chunk.get('text', ''):
                        accumulated_text += text
                        response_msg = gr.ChatMessage(content=accumulated_text)
                        yield [thinking_msg, response_msg] if thinking_msg else response_msg

                # For legacy text only content (when chunk is a string)
                elif isinstance(chunk, str):
                    accumulated_text += chunk
                    yield {"text": accumulated_text}

                await asyncio.sleep(0)  # Add sleep for Gradio UI streaming echo

        except Exception as e:
            logger.error(f"[ChatbotHandlers] Failed to send message: {e}", exc_info=True)
            yield {"text": "I apologize, but I encountered an error. Please try again."}
