import json
from typing import Dict, List, Optional, Iterator, Union
from botocore import exceptions as boto_exceptions
from backend.genai.models import API_BEDROCK_INVOKE, clients
from . import LLMAPIProvider, LLMParameters, GenImageParameters, LLMMessage, LLMResponse, LLMProviderError
from .. import logger


class BedrockInvoke(LLMAPIProvider):
    """Amazon Bedrock LLM provider powered by the invoke model API for single-turn generation."""
    
    def __init__(self, model_id: str, llm_params: Union[LLMParameters, GenImageParameters], tools=None):
        super().__init__(model_id, llm_params, tools)

    def _validate_config(self) -> None:
        """Validate Bedrock-specific configuration"""
        if not self.model_id:
            raise boto_exceptions.ParamValidationError(
                report="Model ID must be specified for Bedrock"
            )

    def _initialize_client(self) -> None:
        """Initialize Bedrock client"""
        try:
            _, provider = clients.resolve(self.model_id)
            self.client = clients.bedrock_runtime_client(provider)
        except Exception as e:
            raise boto_exceptions.ClientError(
                error_response={
                    'Error': {
                        'Code': 'InitializationError',
                        'Message': f"Failed to initialize Bedrock client: {str(e)}"
                    }
                },
                operation_name='initialize_client'
            )

    def _handle_bedrock_error(self, error: boto_exceptions.ClientError):
        """Handle Bedrock-specific errors by raising LLMProviderError
        
        Args:
            error: ClientError exception that occurred during Bedrock API calls
            
        Raises:
            LLMProviderError with error code, user-friendly message, and technical details
        """
        # Extract error details from ClientError
        error_code = error.response.get('Error', {}).get('Code', 'UnknownError')
        error_detail = error.response.get('Error', {}).get('Message', str(error))
        logger.error(f"[BRInvokeProvider] ClientError: {error_code} - {error_detail}")

        # Map error codes to user-friendly messages
        error_messages = {
            'ThrottlingException': "Rate limit exceeded. Please try again later.",
            'TooManyRequestsException': "Too many requests. Please try again later.",
            'ValidationException': "There was an issue with the request format. Please try again with different input.",
            'ModelTimeoutException': "The model took too long to respond. Please try with a shorter message.",
            'ModelNotReadyException': "The model is currently initializing. Please try again in a moment.",
            'ResourceNotFoundException': "This model is no longer available from AWS (retired or not enabled for this account). Please choose another model.",
            'AccessDeniedException': "This model is not enabled for this account. Please choose another model.",
            'ModelStreamErrorException': "Error in model stream. Please try again with different parameters.",
            'ModelErrorException': "The model encountered an error processing your request. Please try again with different input."
        }

        # Get the appropriate message or use a default one
        message = error_messages.get(error_code, f"AWS Bedrock error ({error_code}). Please try again.")
        
        # Raise LLMProviderError with error code, user-friendly message, and technical details
        raise LLMProviderError(error_code, message, error_detail)

    def invoke_model_sync(
        self,
        request_body: Dict,
        accept: str = "application/json",
        content_type: str = "application/json",
        **kwargs
    ) -> Dict:
        """Send a request to Bedrock's invoke model API
        
        Args:
            request_body: Model-specific request parameters
            accept: Response content type
            content_type: Request content type
            **kwargs: Additional parameters
            
        Returns:
            Dict containing model response
        """
        try:
            # Prepare request body
            body = json.dumps(request_body)

            # Invoke model
            logger.debug(f"[BRInvokeProvider] Invoking model {self.model_id}")
            logger.debug(f"--- Request body: {body}")
            resp = self.client.invoke_model(
                modelId=self.model_id,
                body=body,
                accept=accept,
                contentType=content_type
            )
            
            # Parse response
            raw_resp = resp.get('body').read()
            # logger.debug(f"[BRInvokeProvider] Raw response: {raw_resp}")
            return json.loads(raw_resp)
            
        except boto_exceptions.ClientError as e:
            self._handle_bedrock_error(e)
    
    def invoke_model_stream(
        self,
        request_body: Dict,
        accept: str = "application/json",
        content_type: str = "application/json",
        **kwargs
    ) -> Iterator[Dict]:
        """Send a request to Bedrock's invoke model API with streaming
        
        Args:
            request_body: Model-specific request parameters
            accept: Response content type
            content_type: Request content type
            **kwargs: Additional parameters
            
        Yields:
            Dict containing response chunks
        """
        try:
            # Prepare request body
            body = json.dumps(request_body)
            
            # Get streaming response
            response = self.client.invoke_model_with_response_stream(
                modelId=self.model_id,
                body=body,
                accept=accept,
                contentType=content_type
            )
            
            # Stream response chunks
            for chunk in response.get('body'):
                # Parse and yield chunk
                yield json.loads(chunk.get('chunk').get('bytes'))
                
        except boto_exceptions.ClientError as e:
            self._handle_bedrock_error(e)


    def generate_content(
        self,
        messages: List[LLMMessage],
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> LLMResponse:
        """Generate content is not supported by invoke API"""
        raise NotImplementedError(
            "Generate content streaming is not supported by the invoke API. "
            "Use BedrockConverse provider for chat functionality."
        )

    def generate_stream(
        self,
        messages: List[LLMMessage],
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> Iterator[Dict]:
        """Generate stream is not supported by invoke API"""
        raise NotImplementedError(
            "Generate stream is not supported by the invoke API. "
            "Use BedrockConverse provider for chat functionality."
        )

    def multi_turn_generate(
        self,
        message: LLMMessage,
        history: Optional[List[LLMMessage]] = None,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> Iterator[Dict]:
        """Multi-turn generation is not supported by invoke API"""
        raise NotImplementedError(
            "Multi-turn generation is not supported by the invoke API. "
            "Use BedrockConverse provider for chat functionality."
        )


def create_creative_provider(api: str, model_id: str, image_params: GenImageParameters) -> 'BedrockInvoke':
    """Provider for image/video generation, which only Bedrock InvokeModel serves."""
    if api != API_BEDROCK_INVOKE:
        raise ValueError(f"Creative content generation needs {API_BEDROCK_INVOKE}, got: {api}")
    return BedrockInvoke(model_id, image_params, [])


def first_image_b64(response: Dict) -> str:
    """The first generated image; a clear error when the model's content filter returned none."""
    if response.get("images"):
        return response["images"][0]
    if response.get("image"):
        return response["image"]
    reasons = response.get("finish_reasons") or []
    if any("filter" in str(r).lower() for r in reasons):
        raise ValueError(f"The image model's content filter rejected the request ({'; '.join(map(str, reasons))}). "
                         "Rephrase the prompt and try again.")
    raise ValueError(f"The image model returned no image (fields: {list(response)}, finish: {reasons})")
