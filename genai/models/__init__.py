# Copyright iX.
# SPDX-License-Identifier: MIT-0
from typing import Dict, List, Optional, Union, Any
from dataclasses import dataclass, asdict, field


# Model category and capabilities
VAILD_CATEGORY = ['text', 'vision', 'image', 'video', 'reasoning', 'embedding']
VALID_MODALITY = ['text', 'document', 'image', 'video', 'audio']


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
    api_provider: str
    category: str   #Legacy to compatibility with existing models
    vendor: str = ""      # Optional
    description: str = "" # Optional
    capabilities: Optional[LLM_CAPABILITIES] = None

    def __post_init__(self):
        """Validate model attributes after initialization"""
        if not self.name:
            raise ValueError("Model name is required")
        if not self.model_id:
            raise ValueError("Model ID is required")
        if not self.api_provider:
            raise ValueError("API provider is required")
        if not isinstance(self.api_provider, str):
            raise ValueError("API provider must be a string")
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
        capabilities = LLM_CAPABILITIES(**capabilities_data) if capabilities_data else None
        
        # Create instance with remaining data
        return cls(
            name=data['name'],
            model_id=data['model_id'],
            api_provider=data['api_provider'],
            category=data.get('category', 'text'),
            vendor=data.get('vendor', ''),
            description=data.get('description', ''),
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
