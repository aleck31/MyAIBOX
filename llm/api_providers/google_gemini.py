from typing import Dict, List, Optional, Iterator, AsyncIterator
from google import genai
from google.genai import types
from google.api_core import exceptions
from core.logger import logger
from core.config import env_config
from utils.aws import get_secret
from . import LLMAPIProvider, LLMParameters, LLMMessage, LLMResponse, LLMProviderError


class GeminiProvider(LLMAPIProvider):
    """Google Gemini LLM provider implementation"""

    def __init__(self, model_id: str, llm_params: LLMParameters, tools=None):
        """Initialize provider with model ID, parameters and tools

        Args:
            model_id: Model identifier
            llm_params: LLM inference parameters
            tools: Optional list of tool specifications
        """
        super().__init__(model_id, llm_params, tools)

    def _validate_config(self) -> None:
        """Validate Gemini-specific configuration"""
        logger.debug(f"[GeminiProvider] Model Configurations: {self.model_id}, {self.llm_params}")
        if not self.model_id:
            raise exceptions.InvalidArgument(
                "Model ID must be specified for Gemini"
            )

    def _initialize_client(self) -> None:
        """Initialize Gemini client"""
        try:
            gemini_secret_key = env_config.gemini_config['secret_id']
            api_key = get_secret(gemini_secret_key).get('api_key')
            if not api_key:
                raise ValueError("Gemini API key not configured")

            # Initialize client with API key
            self.client = genai.Client(api_key=api_key)

        except Exception as e:
            raise exceptions.FailedPrecondition(f"Failed to initialize Gemini client: {str(e)}")

    def _get_generation_config(self, system_prompt: Optional[str] = None) -> types.GenerateContentConfig:
        """Get Gemini-specific generation configuration"""
        config = types.GenerateContentConfig(
            max_output_tokens=self.llm_params.max_tokens,
            temperature=self.llm_params.temperature,
            top_p=self.llm_params.top_p,
            top_k=self.llm_params.top_k,
            candidate_count=1
        )

        # Add system instruction if provided
        if system_prompt:
            config.system_instruction = system_prompt

        return config

    def _handle_gemini_error(self, error: Exception):
        """Handle Gemini-specific errors by raising LLMProviderError

        Args:
            error: Gemini API exception

        Raises:
            LLMProviderError with error code, user-friendly message, and technical details
        """
        error_code = type(error).__name__
        error_detail = str(error)

        logger.error(f"[GeminiProvider] {error_code} - {error_detail}")

        # Format user-friendly message based on exception type
        if isinstance(error, exceptions.ResourceExhausted):
            message = "The service is currently experiencing high load. Please try again in a moment."
        elif isinstance(error, exceptions.Unauthenticated):
            message = "There was an authentication error. Please try again."
        elif isinstance(error, exceptions.InvalidArgument):
            message = "There was an issue with the request format. Please try again with different input."
        elif isinstance(error, exceptions.FailedPrecondition):
            message = "The request was blocked by safety filters. Please try again with different input."
        elif isinstance(error, exceptions.DeadlineExceeded):
            message = "The request took too long to process. Please try with a shorter message."
        else:
            message = "An unexpected error occurred. Please try again."
            
        # Raise LLMProviderError with error code, user-friendly message, and technical details
        raise LLMProviderError(error_code, message, error_detail)

    def _format_system_prompt(self, system_prompt: str) -> str:
        """Format system prompt"""
        if system_prompt:
            # Clean up the system prompt by removing empty lines and extra whitespace
            return "\n".join([
                instruction.strip() 
                for instruction in system_prompt.split('\n') 
                if instruction.strip()
            ])
        else:
            return ""

    def _convert_messages(
        self,
        messages: List[LLMMessage]
    ) -> List:
        """Convert messages to Gemini-specific format

        Args:
            messages: List of messages to format

        Returns:
            List of Converted messages for Gemini API
        """
        # Convert each message using _convert_message
        return [self._convert_message(msg) for msg in messages]

    def _convert_message(self, message: LLMMessage):
        """Convert a single message into Gemini-specific format

        Args:
            message: Message to format

        Returns:
            Dict with role and parts formatted for Gemini API
        """
        content_parts = []
        
        # Handle context if present and not None
        context = getattr(message, 'context', None)
        if context and isinstance(context, dict):
            context_items = []
            for key, value in context.items():
                if value is not None:
                    # Convert snake_case to spaces and capitalize
                    readable_key = key.replace('_', ' ').capitalize()
                    context_items.append(f"{readable_key}: {value}")
            if context_items:
                # Add formatted context with clear labeling
                content_parts.append(
                    types.Part(text=f"Context Information:\n{' | '.join(context_items)}\n")
                )

        # Handle message content
        if isinstance(message.content, str):
            if message.content.strip():  # Skip empty strings
                content_parts.append(types.Part(text=message.content))
        # Handle multimodal content from Gradio chatbox
        elif isinstance(message.content, dict):
            # Add text if present
            if text := message.content.get("text", "").strip():
                content_parts.append(types.Part(text=text))

            # Add files if present
            if files := message.content.get("files", []):
                for file_path in files:
                    try:
                        # Handle files using client.files.upload
                        file_ref = self.client.files.upload(file=file_path)
                        content_parts.append(types.Part(file_data=types.FileData(
                            file_uri=file_ref.uri,
                            mime_type=file_ref.mime_type
                        )))
                    except Exception as e:
                        logger.error(f"Error uploading file {file_path}: {str(e)}")
                        continue

        role = message.role
        # Convert 'assistant' role to 'model' as required by the new SDK
        if role == 'assistant':
            role = 'model'

        return types.Content(role=role, parts=content_parts)

    def _process_resp_chunk(self, chunk) -> Optional[Dict]:
        """Process a response chunk and return content dict
        
        Args:
            chunk: Response chunk from Gemini
            
        Returns:
            Dict containing response content or None if chunk cannot be processed
        """
        try:
            if hasattr(chunk, 'candidates') and chunk.candidates:
                return {'content': {'text': chunk.candidates[0].content.parts[0].text}}
            return None
        except (AttributeError, IndexError):
            return None

    def _extract_metadata(self, response) -> Optional[Dict]:
        """Extract metadata from response if available"""
        if hasattr(response, 'usage_metadata'):
            metadata = {
                'metadata': {
                    'model': self.model_id,
                    'usage': {
                        'prompt_tokens': response.usage_metadata.prompt_token_count,
                        'completion_tokens': response.usage_metadata.candidates_token_count,
                        'total_tokens': response.usage_metadata.total_token_count
                    }
                }
            }
            
            # Add safety ratings if available
            if (hasattr(response, 'candidates') and response.candidates and 
                hasattr(response.candidates[0], 'safety_ratings') and 
                response.candidates[0].safety_ratings):
                metadata['metadata']['safety_ratings'] = [
                    {r.category: r.probability}
                    for r in response.candidates[0].safety_ratings
                ]
                
            return metadata
        return None

    def _generate_content_sync(
        self,
        messages: List[LLMMessage],
        system_prompt: Optional[str] = '',
        **kwargs
    ) -> LLMResponse:
        """Synchronous implementation of content generation"""
        try:
            llm_messages = self._convert_messages(messages)
            logger.debug(f"Converted messages: {llm_messages}")
            
            # Get generation config with system prompt if provided
            config = self._get_generation_config(
                self._format_system_prompt(system_prompt) if system_prompt else None
            )
            
            # Generate response using generate_content
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=llm_messages,
                config=config
            )

            logger.debug(f"Raw Gemini response: {response}")
            
            # Extract metadata (already includes safety ratings if available)
            metadata = self._extract_metadata(response)
            
            return LLMResponse(
                content=response.text,
                metadata=metadata['metadata'] if metadata else None
            )
            
        except Exception as e:
            self._handle_gemini_error(e)

    def _generate_stream_sync(
        self,
        messages: List[LLMMessage],
        system_prompt: Optional[str] = '',
        **kwargs
    ) -> Iterator[Dict]:
        """Synchronous implementation of streaming generation"""
        try:
            llm_messages = self._convert_messages(messages)
            logger.debug(f"Converted messages: {llm_messages}")
            
            # Get generation config with system prompt if provided
            config = self._get_generation_config(
                self._format_system_prompt(system_prompt) if system_prompt else None
            )

            # Generate streaming using generate_content_stream
            for chunk in self.client.models.generate_content_stream(
                model=self.model_id,
                contents=llm_messages,
                config=config
            ):
                # Stream response content chunks
                if content_dict := self._process_resp_chunk(chunk):
                    yield content_dict

                # Extract usage metadata if available 
                if metadata := self._extract_metadata(chunk):
                    yield metadata
                    
        except Exception as e:
            self._handle_gemini_error(e)

    async def generate_content(
        self,
        messages: List[LLMMessage],
        system_prompt: Optional[str] = '',
        **kwargs
    ) -> LLMResponse:
        """Generate a response from Gemini using generate_content"""
        return self._generate_content_sync(messages, system_prompt, **kwargs)

    async def generate_stream(
        self,
        messages: List[LLMMessage],
        system_prompt: Optional[str] = '',
        **kwargs
    ) -> AsyncIterator[Dict]:
        """Generate a streaming response from Gemini using generate_content with stream=True"""
        for chunk in self._generate_stream_sync(messages, system_prompt, **kwargs):
            yield chunk

    async def multi_turn_generate(
        self,
        message: LLMMessage,
        history: Optional[List[LLMMessage]] = [],
        system_prompt: Optional[str] = '',
        **kwargs
    ) -> AsyncIterator[Dict]:
        """Generate streaming response using multi-turn chat
        Args:
            message: Current user message
            history: Optional chat history
            system_prompt: Optional system instructions
            **kwargs: Additional parameters for inference
            
        Yields:
            Dict containing either:
            - {"content": dict} for content chunks
            - {"metadata": dict} for response metadata
        """
        try:
            # Format history messages
            history_messages = self._convert_messages(history) if history else []
            logger.debug(f"[GeminiProvider] Converted history messages: {history_messages}")

            # Format current user message
            current_message = self._convert_message(message)
            logger.debug(f"[GeminiProvider] Converted Current message: {current_message}")

            # Create chat session with history
            formatted_system_prompt = self._format_system_prompt(system_prompt) if system_prompt else None

            # Create chat with history and system prompt if provided
            chat_args = {
                'model': self.model_id,
                'history': history_messages
            }

            # Add system instruction if provided
            if formatted_system_prompt:
                chat_args['config'] = {
                    'system_instruction': formatted_system_prompt
                }

            chat = self.client.chats.create(**chat_args)

            logger.info(f"[GeminiProvider] Processing multi-turn chat with {len(history_messages)+1} messages")
            
            # Generate streaming using send_message
            # Extract parts from the Content object as send_message_stream expects parts, not Content
            message_parts = current_message.parts

            for chunk in chat.send_message_stream(
                message=message_parts
            ):
                # Stream response chunks
                if content_dict := self._process_resp_chunk(chunk):
                    yield content_dict

                # Extract usage metadata if available 
                if metadata := self._extract_metadata(chunk):
                    yield metadata

        except Exception as e:
            self._handle_gemini_error(e)
