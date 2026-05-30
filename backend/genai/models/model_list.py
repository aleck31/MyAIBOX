"""
LLM model configurations
"""
from . import LLMModel, LLM_CAPABILITIES


# Default model list
DEFAULT_MODELS = [
    LLMModel(
        name='claude-sonnet-4-6',
        model_id='global.anthropic.claude-sonnet-4-6',
        api_provider='Bedrock',
        category='vision',
        description='Claude Sonnet 4.6 model with extended thinking and vision capabilities.',
        vendor='Anthropic',
        capabilities=LLM_CAPABILITIES(
            input_modality=['text', 'image', 'document'],
            output_modality=['text'],
            streaming=True,
            tool_use=True,
            reasoning=True,
            context_window=200*1024
        )
    ),
    LLMModel(
        name='Gemini 2.5 Pro',
        model_id='gemini-2.5-pro',
        api_provider='Gemini',
        category='vision',
        description="Google's flagship model with 1M context window. Strong at reasoning, coding, and multimodal tasks.",
        vendor='Google',
        capabilities=LLM_CAPABILITIES(
            input_modality=['text', 'image', 'audio', 'video'],
            output_modality=['text'],
            streaming=True,
            tool_use=True,
            reasoning=True,
            context_window=1048576
        )
    ),
    LLMModel(
        name='gemini flash latest',
        model_id='gemini-flash-latest',
        api_provider='Gemini',
        category='vision',
        description='Gemini Flash latest model for text and vision',
        vendor='Google',
        capabilities=LLM_CAPABILITIES(
            input_modality=['text', 'image', 'document'],
            output_modality=['text'],
            streaming=True,
            tool_use=True,
            context_window=1024*1024
        )
    ),
    LLMModel(
        name= "Nova Pro",
        category='vision',
        api_provider= "Bedrock",
        description= "Nova Pro is a vision understanding foundation model. It is multilingual and can reason over text, images and videos.",
        model_id= "us.amazon.nova-pro-v1:0",
        vendor= "Amazon",
        capabilities=LLM_CAPABILITIES(
            input_modality=['text', 'image', 'video'],
            output_modality=['text'],
            streaming=True,
            tool_use=True
        )
    ),
    LLMModel(
        name= "Nova Canvas",
        category='image',
        api_provider= "BedrockInvoke",
        description= "Nova image generation model. It generates images from text and allows users to upload and edit an existing image. ",
        model_id= "amazon.nova-canvas-v1:0",
        vendor= "Amazon",
        capabilities=LLM_CAPABILITIES(
            input_modality=['text', 'image'],
            output_modality=['image']
        )
    ),
    LLMModel(
        name='Stable Image Ultra',
        model_id='stability.stable-image-ultra-v1:1',
        api_provider='BedrockInvoke',
        category='image',
        description="Stability AI's highest quality text-to-image model.",
        vendor='Stability AI',
        region='us-west-2',
        capabilities=LLM_CAPABILITIES(
            input_modality=['text'],
            output_modality=['image']
        )
    ),
    LLMModel(
        name= "Nova Reel",
        category='video',
        api_provider= "BedrockInvoke",
        description= "Nova video generation model. It generates short high-definition videos, up to 9 seconds long from input images or a natural language prompt.",
        model_id= "amazon.nova-reel-v1:0",
        vendor= "Amazon",
        capabilities=LLM_CAPABILITIES(
            input_modality=['text', 'image'],
            output_modality=['video']
        )
    ),
    LLMModel(
        name='DeepSeek V3.2',
        model_id='deepseek.v3.2',
        api_provider='Bedrock',
        category='text',
        description="DeepSeek's flagship MoE model. Strong at reasoning, coding, math, multilingual.",
        vendor='DeepSeek',
        capabilities=LLM_CAPABILITIES(
            input_modality=['text'],
            output_modality=['text'],
            streaming=True,
            tool_use=True,
            reasoning=True,
            context_window=128000
        )
    ),
    LLMModel(
        name='Nova Sonic',
        model_id='amazon.nova-2-sonic-v1:0',
        api_provider='BedrockSonic',
        category='realtime',
        description='Amazon Nova Sonic speech-to-speech model for real-time voice conversation.',
        vendor='Amazon',
        region='us-east-1',  # Nova Sonic is only available in us-east-1
        capabilities=LLM_CAPABILITIES(
            input_modality=['audio', 'text'],
            output_modality=['audio'],
            streaming=True,
            tool_use=True,
            context_window=32*1024
        )
    )
]
