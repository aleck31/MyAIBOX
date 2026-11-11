# Copyright iX.
# SPDX-License-Identifier: MIT-0
import re
from typing import Dict, List, Optional, Union, Any
from dataclasses import dataclass, asdict, field
from backend.common.logger import setup_logger

logger = setup_logger('models')


# Model category and capabilities
# category = what the model is FOR; reasoning/tool_use/etc. are capabilities, not categories.
VAILD_CATEGORY = ['text', 'vision', 'image', 'video', 'embedding', 'realtime']
VALID_MODALITY = ['text', 'document', 'image', 'video', 'audio']

# The API a model is called with; the provider says where and with which credentials.
API_BEDROCK_CONVERSE = 'bedrock-converse'
API_BEDROCK_INVOKE = 'bedrock-invoke'
API_BEDROCK_BIDI = 'bedrock-bidi-stream'  # InvokeModelWithBidirectionalStream (Nova Sonic)
API_OPENAI_RESPONSES = 'openai-responses'
API_OPENAI_CHAT = 'openai-chat-completions'
API_ANTHROPIC_MESSAGES = 'anthropic-messages'
API_GEMINI = 'gemini'
VALID_APIS = (API_BEDROCK_CONVERSE, API_BEDROCK_INVOKE, API_BEDROCK_BIDI, API_OPENAI_RESPONSES,
              API_OPENAI_CHAT, API_ANTHROPIC_MESSAGES, API_GEMINI)
BEDROCK_APIS = (API_BEDROCK_CONVERSE, API_BEDROCK_INVOKE, API_BEDROCK_BIDI)

AUTH_AWS = 'aws'          # SigV4 with the host's AWS credentials
AUTH_API_KEY = 'api_key'  # a key sent as a Bearer token (x-goog-api-key for Gemini)
VALID_AUTH = (AUTH_AWS, AUTH_API_KEY)


@dataclass
class LLMProvider:
    """Where models are called and how: endpoint, credentials and the APIs it serves."""
    name: str
    auth: str
    apis: List[str] = field(default_factory=list)
    base_url: str = ""     # empty = the API's official endpoint
    region: str = ""       # AWS region (Bedrock APIs)
    api_key: str = ""      # inline key; prefer secret_name
    secret_name: str = ""  # Secrets Manager secret: {"api_key": "..."} or the bare key

    def __post_init__(self):
        if not re.fullmatch(r'[A-Za-z0-9._-]{1,64}', self.name or ''):
            raise ValueError("Provider name must be 1-64 letters, digits, '.', '_' or '-'")
        if self.auth not in VALID_AUTH:
            raise ValueError(f"Invalid auth. Must be one of: {VALID_AUTH}")
        if not self.apis or any(a not in VALID_APIS for a in self.apis):
            raise ValueError(f"Provider APIs must be a non-empty subset of: {VALID_APIS}")
        if self.auth == AUTH_AWS:
            if any(a not in BEDROCK_APIS for a in self.apis):
                raise ValueError("AWS credentials only work with Bedrock APIs")
            if not self.region:
                raise ValueError("Region is required for AWS credentials")
        elif API_BEDROCK_BIDI in self.apis:
            raise ValueError(f"{API_BEDROCK_BIDI} needs AWS credentials")
        elif not (self.api_key or self.secret_name):
            raise ValueError("An API key or a secret name is required")
        if self.api_key and self.secret_name:
            raise ValueError("Set either an API key or a secret name, not both")

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> 'LLMProvider':
        return cls(**{k: data[k] for k in cls.__dataclass_fields__ if k in data})


@dataclass
class LLM_CAPABILITIES:
    """Model capabilities configuration"""
    input_modality: List[str] = field(default_factory=lambda: ['text']) # Support input modalities
    output_modality: List[str] = field(default_factory=lambda: ['text'])  # Support output modalities
    context_window: Optional[int] = 128 * 1024  # Maximum tokens(context window) size
    streaming: Optional[bool] = True  # Support for streaming responses
    tool_use: Optional[bool] = False  # Support for tool use / function calling
    reasoning: Optional[bool] = False  # Support for reasoning (extended thinking)


@dataclass
class LLMModel:
    """Represents an LLM model configuration with capabilities"""
    name: str
    model_id: str
    provider: str   # LLMProvider.name
    api: str        # one of VALID_APIS, served by the provider
    category: str
    vendor: str = ""      # Optional
    description: str = "" # Optional
    enabled: bool = True  # Disabled models are hidden from dropdowns but kept in storage
    service_tier: str = ""  # Bedrock Converse service tier, e.g. "flex"; empty = standard
    capabilities: LLM_CAPABILITIES = field(default_factory=LLM_CAPABILITIES)

    def __post_init__(self):
        """Validate model attributes after initialization"""
        if not self.name:
            raise ValueError("Model name is required")
        if not self.model_id:
            raise ValueError("Model ID is required")
        if not self.provider:
            raise ValueError("Provider is required")
        if self.api not in VALID_APIS:
            raise ValueError(f"Invalid API. Must be one of: {VALID_APIS}")
        if self.service_tier and self.api != API_BEDROCK_CONVERSE:
            raise ValueError(f"Service tier only applies to {API_BEDROCK_CONVERSE}")
        if self.category not in VAILD_CATEGORY:
            raise ValueError(f"Invalid model category. Must be one of: {VAILD_CATEGORY}")

        # Initialize capabilities if none provided
        self.capabilities = self.capabilities or LLM_CAPABILITIES()

    def supports_input(self, modality: str) -> bool:
        """Check if model supports a specific input modality"""
        if self.capabilities is None:
            return False
        return modality in self.capabilities.input_modality

    def supports_output(self, modality: str) -> bool:
        """Check if model supports a specific output modality"""
        if self.capabilities is None:
            return False
        return modality in self.capabilities.output_modality

    def get_capability(self, name: str) -> Any:
        """Get a capability value by name"""
        if self.capabilities is None:
            raise ValueError("Capabilities are not initialized")
        if not hasattr(self.capabilities, name):
            raise ValueError(f"Invalid capability name: {name}")
        return getattr(self.capabilities, name)

    def to_dict(self) -> Dict:
        """Convert to dictionary for storage, excluding None values"""
        data = {k: v for k, v in asdict(self).items() if v is not None}
        # Convert capabilities to dict if present
        if self.capabilities:
            data['capabilities'] = asdict(self.capabilities)
        return data

    @classmethod
    def from_dict(cls, data: Dict) -> 'LLMModel':
        """Create from dictionary"""
        # Make a copy to avoid modifying the input
        data = data.copy()
        
        # Extract and convert capabilities data if present
        capabilities_data = data.pop('capabilities', None)
        capabilities = LLM_CAPABILITIES(**capabilities_data)

        # Create instance with remaining data
        return cls(
            name=data['name'],
            model_id=data['model_id'],
            provider=data['provider'],
            api=data['api'],
            category=data.get('category', 'text'),
            vendor=data.get('vendor', ''),
            description=data.get('description', ''),
            enabled=data.get('enabled', True),
            service_tier=data.get('service_tier', ''),
            capabilities=capabilities
        )


@dataclass
class LLMMessage:
    """LLM message structure"""
    role: str
    content: Union[str, Dict]
    context: Optional[Dict] = None    
    metadata: Optional[Dict] = None

    def to_dict(self) -> Dict:
        """Convert message to dictionary, excluding None values"""
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class LLMParameters:
    """LLM inference parameters configuration"""
    max_tokens: int = 4096  # maximum number of tokens to generate. Responses are not guaranteed to fill up to the maximum desired length.
    temperature: float = 0.9  # tunes the degree of randomness in generation. Lower temperatures mean less random generations.
    top_p: float = 0.99   # less than one keeps only the smallest set of most probable tokens with probabilities that add up to top_p or higher for generation.
    top_k: Optional[int] = 100 # Lower values produce more conservative and focused outputs, while higher values introduce diversity and creativity.
    thinking: Optional[Dict] = None # Reasoning Parameters for reasoning models，such claude 3.7
    stop_sequences: Optional[List[str]] = None  # stop_sequences - are sequences where the API will stop generating further tokens. The returned text will not contain the stop sequence.

    def to_dict(self) -> Dict:
        """Convert config to dictionary, excluding None values"""
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class GenImageParameters:
    """LLM inference parameters for Image Generation"""
    height: Optional[int] = None  # Height of the generated image
    width: Optional[int] = None  # Width of the generated image
    aspect_ratio: Optional[str] = '16:9'  # Aspect ratio of the generated image
    img_number: Optional[int] = 1  # The number of images to generate
    cfg_scale: Optional[float] = 6.5  # Specifies how strongly the generated image should adhere to the prompt

    def to_dict(self) -> Dict:
        """Convert config to dictionary, excluding None values"""
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class LLMResponse:
    """Basic LLM response structure"""
    content: Dict # text, image, video, file_path
    thinking: Optional[str] = None  # Thinking text from Reasoning models
    metadata: Optional[Dict] = None


@dataclass
class ResponseMetadata:
    """Metadata structure for LLM responses with stop_reason"""
    stop_reason: Optional[str] = None
    usage: Optional[Dict] = None
    metrics: Optional[Dict] = None
    performance_config: Optional[Dict] = None

    def update_from_chunk(self, chunk_metadata: Dict) -> None:
        """Update metadata fields from a chunk"""
        self.usage = chunk_metadata.get('usage', self.usage)
        self.metrics = chunk_metadata.get('metrics', self.metrics)
        self.performance_config = chunk_metadata.get('performanceConfig', self.performance_config)

    def to_dict(self) -> Dict:
        """Convert metadata to dictionary, excluding None values"""
        return {k: v for k, v in asdict(self).items() if v is not None}
