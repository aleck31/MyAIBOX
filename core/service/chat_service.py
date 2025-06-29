from datetime import datetime
from itertools import groupby
from typing import Dict, List, Optional, AsyncIterator
from core.logger import logger
from core.session import Session
from genai.models.api_providers import LLMMessage, LLMProviderError
from genai.models.model_manager import model_manager
from . import BaseService


class ChatService(BaseService):
    """Chat service implementation with streaming capabilities"""

    def __init__(
        self,
        module_name: str,
        cache_ttl: int = 600  # 10 minutes default TTL
    ):
        """Initialize ChatService
        
        Args:
            module_name: Name of the module using this service
            cache_ttl: Cache time-to-live in seconds
        """
        super().__init__(module_name=module_name, cache_ttl=cache_ttl)

    # File type definitions
    _FILE_TYPES = {
        ('.png', '.jpg', '.jpeg', '.gif', '.webp'): ('image', '[User shared an image]', '[Generated an image in response]'),
        ('.mp4', '.mov', '.webm'): ('video', '[User shared a video]', '[Generated a video in response]'),
        ('.pdf', '.doc', '.docx'): ('document', '[User shared a document]', '[Generated a document in response]')
    }
    # Maximum number of context messages to include by default
    _max_context_messages: int = 24

    def _prepare_chat_message(
        self, 
        role: str, 
        content: Dict, 
        model_id: Optional[str] = None,
        context: Optional[Dict] = None, 
        metadata: Optional[Dict] = None
    ) -> LLMMessage:
        """Create standardized interaction entry with content filtering based on model capabilities.
        
        Note:
            Creates a Message instance with role and content.
            Filters content based on model's supported input modalities.
            Optional context and metadata can be provided for additional information.
        """
        # Get model capabilities if model_id provided
        if model_id and isinstance(content, dict) and 'files' in content:
            model = model_manager.get_model_by_id(model_id)
            if model and model.capabilities:
                supported_modalities = model.capabilities.input_modality
                # Remove files for text-only models
                if len(supported_modalities) == 1 and supported_modalities[0] == 'text':
                    content.pop('files')
                    content['text'] = (content.get('text', '') + 
                        "\n[Note: Files were removed as the current model does not support multimodal content.]").strip()

        return LLMMessage(
            role=role,
            content=content,
            context=context,
            metadata=metadata
        )

    def _prepare_history(self, ui_history: List[Dict], max_messages: Optional[int] = None) -> List[LLMMessage]:
        """Format and process history messages for LLM consumption.
 
        Args:
            ui_history: List of message dictionaries from UI state
            max_messages: Maximum number of messages to include (defaults to self._max_context_messages)
            
        Returns:
            List of processed and truncated LLMMessage objects that starts with a user message
            
        Note:
            1. Messages are grouped by role and their content is combined with newlines
            2. File content is converted to descriptive text using _get_file_desc
            3. History is truncated to respect max_messages limit
            4. Ensures the first message is from a user (required by some LLM providers)
        """
        if not ui_history:
            return []

        # Step 1: Convert UI history to LLMMessage objects
        history_messages = []
        for role, group in groupby(ui_history, key=lambda x: x["role"]):
            texts = []
            for msg in group:
                content = msg.get("content")
                if not content:
                    continue
                    
                if isinstance(content, str):
                    texts.append(content)
                elif isinstance(content, (list, tuple)):
                    texts.extend(self._get_file_desc(f, role) for f in content)
                elif isinstance(content, dict):
                    if text := content.get("text"):
                        texts.append(text)
                    if files := content.get("files"):
                        texts.extend(self._get_file_desc(f, role) for f in files)
                
            if texts:
                history_messages.append(self._prepare_chat_message(
                    role=role,
                    content={"text": "\n".join(texts)}
                ))
        
        # Step 2: Apply truncation if needed
        # Use class default if max_messages not specified
        if max_messages is None:
            max_messages = self._max_context_messages

        # If we have more messages than the limit, truncate
        if len(history_messages) > max_messages:
            # Take the last max_messages
            truncated_msgs = history_messages[-max_messages:]

            # Step 3: Ensure the truncated history starts with a user message
            if truncated_msgs and truncated_msgs[0].role != "user":
                truncated_msgs.pop(0)

            return truncated_msgs

        else:
            return history_messages

    def _get_file_desc(self, file_path: str, role: str) -> str:
        """Get standardized file description based on type and role.
        
        Note:
            Returns appropriate description based on file extension and role.
            Empty string is returned for unrecognized file types.
        """
        file_path = file_path.lower()
        if matching_exts := next((exts for exts, _ in self._FILE_TYPES.items() if file_path.endswith(exts)), None):
            _, user_desc, assistant_desc = self._FILE_TYPES[matching_exts]
            return user_desc if role == 'user' else assistant_desc
        return ''

    async def get_session_role(self, session: Session) -> str:
        """Get persona role from session context
        
        Args:
            session: Session to get persona role for
            
        Returns:
            str: persona role if found, 'default' otherwise
        """
        try:
            # Get persona role from session context
            if style := session.context.get('persona_role'):
                logger.debug(f"[ChatService] Get session persona role: {style}")
                return style
            else:
                logger.debug(f"[ChatService] No persona role found, using default")
                return 'default'

        except Exception as e:
            logger.error(f"[ChatService] Failed to get persona role for session {session.session_id}: {str(e)}")
            return 'default'
            
    async def update_session_role(self, session: Session, style: str) -> None:
        """Update persona role in session context
        
        Args:
            session: Session to update
            style: New persona role to set
        """
        try:
            session.context['persona_role'] = style
            await self.session_store.save_session(session)
            logger.debug(f"[ChatService] Updated persona role to {style} in session {session.session_id}")
        except Exception as e:
            logger.error(f"[ChatService] Failed to update session style: {str(e)}")
            raise
            
    async def clear_history(self, session: Session) -> None:
        """Clear chat history for a session
        
        Args:
            session: Active chat session to clear history for
            
        Note:
            - Clears the history list
            - Resets interaction count
            - Updates timestamp
            - Persists changes to session store
        """
        session.history = []  # Clear message history
        # session.context['total_interactions'] = 0  # Reset interaction count
        await self.session_store.save_session(session)
        logger.debug(f"[ChatService] Cleared history for session {session.session_id}")

    async def streaming_reply(
        self,
        session: Session,
        ui_input: Dict,
        ui_history: Optional[List[Dict]] = [],
        style_params: Optional[Dict] = None
    ) -> AsyncIterator[Dict]:
        """Process user message and stream assistant's response
        
        Args:
            session: Active chat session
            ui_input: Dict with text and/or files
            ui_history: List of message dictionaries with role and content fields from UI state
            style_params: LLM generation parameters

        Yields:
            Message chunks for handler
        """
        try:
            # Get LLM provider with model fallback
            model_id = await self.get_session_model(session)

            # Convert new message to chat Message format
            user_message = self._prepare_chat_message(
                role="user",
                content=ui_input,
                model_id=model_id,  # Pass model_id for content filtering
                context={
                    'local_time': datetime.now().astimezone().isoformat(),
                    'user_name': session.user_name
                }
            )
            logger.debug(f"[ChatService] User message sent to LLM Provider: {user_message}")

            # Convert history messages to chat Message format with truncation
            history_messages = self._prepare_history(ui_history)
                
            logger.debug(f"[ChatService] History messages sent to LLM Provider: {len(history_messages)} messages")

            # Get LLM provider
            provider = self._get_model_provider(model_id)
            logger.debug(f"[ChatService] Using LLM provider: {provider.__class__.__name__}")

            # Track response state
            accumulated_text = []
            accumulated_files = []
            response_metadata = {}
            
            # Stream from LLM
            logger.debug(f"[ChatService] Streaming with model {model_id} and params: {style_params}")
            try:
                async for chunk in provider.multi_turn_generate(
                    message=user_message,
                    history=history_messages,
                    system_prompt=session.context.get('system_prompt'),
                    **(style_params or {})
                ):
                    if not isinstance(chunk, dict):
                        logger.warning(f"[ChatService] Unexpected chunk type: {type(chunk)}")
                        continue

                    # Pass through thinking or content chunks
                    if thinking := chunk.get('thinking'):
                        yield {'thinking': thinking}
                    elif content := chunk.get('content', {}):
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

                # Add complete interaction to session after successful LLM response
                if accumulated_text or accumulated_files:
                    # Add user message and assistant message in order
                    session.add_interaction(user_message.to_dict())
                    assistant_message = self._prepare_chat_message(
                        role="assistant",
                        content={
                            "text": ''.join(accumulated_text),
                            "files": accumulated_files
                        },
                        metadata=response_metadata or None
                    )
                    session.add_interaction(assistant_message.to_dict())
                    # Persist to session store
                    await self.session_store.save_session(session)

            except LLMProviderError as e:
                # Log error with code and details
                logger.error(f"[ChatService] LLM error in session {session.session_id}: {e.error_code}")
                # Yield user-friendly message from provider
                yield {"text": f"I apologize, {e.message}"}

        except Exception as e:
            # Log session-level errors
            logger.error(f"[ChatService] Session error in {session.session_id}: {str(e)}")
            yield {"text": "I apologize, but I encountered a session error. Please try again."}
