from typing import Dict, List, Optional, Iterator
import openai
from openai import OpenAI
from backend.core.config import env_config
from backend.utils.aws import get_secret
from backend.genai.models.model_manager import model_manager
from . import LLMAPIProvider, LLMParameters, LLMMessage, LLMResponse, LLMProviderError
from .. import logger


class OpenAIResponsesProvider(LLMAPIProvider):
    """OpenAI-compatible models on the Responses API (e.g. GPT-5 via Bedrock Mantle).

    Same wire protocol as OpenAIProvider but uses the Responses API and a per-model
    base_url + Bedrock API key, since GPT-5 rejects /chat/completions.
    """

    def __init__(self, model_id: str, llm_params: LLMParameters, tools=None):
        super().__init__(model_id, llm_params, tools)
        self.llm_params: LLMParameters = llm_params

    def _validate_config(self) -> None:
        if not self.model_id:
            raise ValueError("Model ID must be specified for OpenAIResponses")

    def _initialize_client(self) -> None:
        try:
            model = model_manager.get_model_by_id(self.model_id)
            if not model or not getattr(model, 'base_url', ''):
                raise ValueError(f"Model {self.model_id} requires a base_url")
            secret_id = env_config.bedrock_config.get('secret_id')
            api_key = get_secret(secret_id).get('api_key') if secret_id else None
            if not api_key:
                raise ValueError("Bedrock API key not configured (Secrets Manager)")
            self.client = OpenAI(base_url=model.base_url, api_key=api_key)
        except Exception as e:
            raise ValueError(f"Failed to initialize OpenAIResponses client: {str(e)}")

    def _handle_openai_error(self, error: Exception):
        error_code = type(error).__name__
        error_detail = str(error)
        logger.error(f"[OpenAIResponsesProvider] {error_code} - {error_detail}")
        if isinstance(error, openai.RateLimitError):
            message = "Rate limit exceeded. Please try again later."
        elif isinstance(error, openai.AuthenticationError):
            message = "Authentication failed. Please check the Bedrock API key."
        elif isinstance(error, openai.BadRequestError):
            message = "Invalid request format. Please try again with different input."
        elif isinstance(error, openai.APITimeoutError):
            message = "The request timed out. Please try again."
        elif isinstance(error, openai.APIConnectionError):
            message = "Failed to connect to the API. Please check your network."
        else:
            message = "An unexpected error occurred. Please try again."
        raise LLMProviderError(error_code, message, error_detail)

    def _convert_messages(self, messages: List[LLMMessage], system_prompt: Optional[str] = None) -> List[Dict]:
        """Flatten messages to the Responses API input array (role + text content)."""
        out: List[Dict] = []
        if system_prompt:
            out.append({"role": "system", "content": system_prompt})
        for msg in messages:
            content = msg.content
            if isinstance(content, dict):
                content = content.get("text", "")
            ctx = getattr(msg, 'context', None)
            if ctx and isinstance(ctx, dict):
                items = [f"{k.replace('_', ' ').capitalize()}: {v}" for k, v in ctx.items() if v is not None]
                if items:
                    content = f"Context Information:\n{' | '.join(items)}\n{content}"
            out.append({"role": msg.role, "content": str(content)})
        return out

    def generate_content(self, messages: List[LLMMessage], system_prompt: Optional[str] = None, **kwargs) -> LLMResponse:
        try:
            response = self.client.responses.create(
                model=self.model_id,
                input=self._convert_messages(messages, system_prompt),  # type: ignore[arg-type]
                max_output_tokens=kwargs.get('max_tokens', self.llm_params.max_tokens),
            )
            usage = getattr(response, 'usage', None)
            metadata = {'model': self.model_id, 'usage': {
                'prompt_tokens': getattr(usage, 'input_tokens', None),
                'completion_tokens': getattr(usage, 'output_tokens', None),
                'total_tokens': getattr(usage, 'total_tokens', None),
            } if usage else None}
            return LLMResponse(content={"text": response.output_text or ""}, metadata=metadata)
        except Exception as e:
            self._handle_openai_error(e)

    def generate_stream(self, messages: List[LLMMessage], system_prompt: Optional[str] = None, **kwargs) -> Iterator[Dict]:
        try:
            for ev in self.client.responses.create(
                model=self.model_id,
                input=self._convert_messages(messages, system_prompt),  # type: ignore[arg-type]
                max_output_tokens=kwargs.get('max_tokens', self.llm_params.max_tokens),
                stream=True,
            ):
                if ev.type == 'response.output_text.delta' and ev.delta:
                    yield {'content': {'text': ev.delta}}
                elif ev.type == 'response.completed':
                    yield {'metadata': {'stop_reason': 'stop'}}
        except Exception as e:
            self._handle_openai_error(e)

    def multi_turn_generate(self, message: LLMMessage, history: Optional[List[LLMMessage]] = None,
                            system_prompt: Optional[str] = None, **kwargs) -> Iterator[Dict]:
        try:
            messages = list(history or [])
            messages.append(message)
            yield from self.generate_stream(messages, system_prompt, **kwargs)
        except Exception as e:
            self._handle_openai_error(e)
