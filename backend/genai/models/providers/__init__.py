# Copyright iX.
# SPDX-License-Identifier: MIT-0
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Union, Iterator
from backend.genai.models import LLMParameters, GenImageParameters, LLMMessage, LLMResponse


class LLMProviderError(Exception):
    """Custom exception for LLM API provider errors with error code and user-friendly message"""
    def __init__(self, error_code: str, message: str, details: Optional[str] = None):
        """Initialize LLMProviderError
        
        Args:
            error_code: Error code (e.g. ThrottlingException, ValidationException)
            message: User-friendly error message
            details: Optional technical details for logging
        """
        self.error_code = error_code
        self.message = message
        self.details = details
        super().__init__(message)


class LLMAPIProvider(ABC):
    """Base class for LLM API providers"""
    
    def __init__(self, model_id: str, llm_params: Union[LLMParameters, GenImageParameters], tools):
        """Initialize provider with model ID, parameters and tools
        
        Args:
            model_id: Model identifier
            llm_params: LLM inference parameters (either LLMParameters for text or GenImageParameters for images)
            tools: List of tool module names to enable
        """
        self.model_id = model_id
        self.llm_params = llm_params
        self.tools = tools
        self._validate_config()
        self._initialize_client()
    
    @abstractmethod
    def _validate_config(self) -> None:
        """Validate provider-specific configuration"""
        pass
    
    @abstractmethod
    def _initialize_client(self) -> None:
        """Initialize provider-specific client"""
        pass
    
    @abstractmethod
    def generate_content(
        self,
        messages: List[LLMMessage],
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> LLMResponse:
        """Generate a response
        Args:
            messages: user messages
            system_prompt: Optional system instructions
            **kwargs: Additional parameters for inference
            
        Return:
            LLMResponse containing the generated content
        """        
        pass

    @abstractmethod
    def generate_stream(
        self,
        messages: List[LLMMessage],
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> Iterator[Dict]:
        """Generate a streaming response (synchronous)
        Args:
            messages: user messages
            system_prompt: Optional system instructions
            **kwargs: Additional parameters for inference

        Yields:
            Dict containing either:
            - {"content": dict} for content chunks
            - {"metadata": dict} for response metadata        
        """
        pass

    @abstractmethod
    def multi_turn_generate(
        self,
        message: LLMMessage,
        history: List[LLMMessage],
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> Iterator[Dict]:
        """Generate streaming response for multi-turn chat (synchronous)
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
        pass


def create_model_provider(api: str, model_id: str, llm_params: LLMParameters, tools: Optional[List[str]] = None) -> LLMAPIProvider:
    """Text-generation provider for a model's API (`LLMModel.api`); its provider supplies endpoint and credentials."""
    from backend.genai.models import (API_BEDROCK_CONVERSE, API_BEDROCK_INVOKE, API_GEMINI, API_OPENAI_CHAT,
                                      API_OPENAI_RESPONSES, API_ANTHROPIC_MESSAGES)
    from backend.genai.models.providers.anthropic_messages import AnthropicMessagesProvider
    from backend.genai.models.providers.bedrock_converse import BedrockConverse
    from backend.genai.models.providers.bedrock_invoke import BedrockInvoke
    from backend.genai.models.providers.google_gemini import GeminiProvider
    from backend.genai.models.providers.openai import OpenAIProvider
    from backend.genai.models.providers.openai_responses import OpenAIResponsesProvider

    providers = {
        API_BEDROCK_CONVERSE: BedrockConverse,
        API_BEDROCK_INVOKE: BedrockInvoke,
        API_ANTHROPIC_MESSAGES: AnthropicMessagesProvider,
        API_GEMINI: GeminiProvider,
        API_OPENAI_CHAT: OpenAIProvider,
        API_OPENAI_RESPONSES: OpenAIResponsesProvider,
    }
    provider_class = providers.get(api)
    if not provider_class:
        raise ValueError(f"Unsupported API for text generation: {api}")

    # Create provider instance with tools
    # Tools will be initialized by the specific provider
    return provider_class(model_id, llm_params, tools or [])
