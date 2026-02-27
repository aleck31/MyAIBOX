"""Service for AI image generation"""
import io
import json
import base64
from PIL import Image
from typing import Dict, Optional, Any
from core.session import Session
from core.module_config import module_config
from genai.models.providers import LLMProviderError
from genai.models.model_manager import model_manager
from . import BaseService, logger


class DrawService(BaseService):
    """Service for AI image generation using Text-to-Image models"""

    def __init__(
        self,
        module_name: str = 'draw',
        cache_ttl: int = 600  # 10 minutes default TTL
    ):
        """Initialize draw service
        
        Args:
            module_name: Name of the module using this service (defaults to 'draw')
            cache_ttl: Cache time-to-live in seconds
        """
        super().__init__(module_name=module_name, cache_ttl=cache_ttl)

    def _validate_model(self, model_id: str, api_provider: str) -> None:
        """Validate model supports image generation
        
        Args:
            model_id: Model ID to validate
            api_provider: API provider name
            
        Raises:
            ValueError: If model is not supported for image generation
        """
        supported = ('BedrockInvoke', 'Gemini')
        if api_provider not in supported:
            raise ValueError(f"Image generation not supported for provider {api_provider}. Supported: {supported}")

    # Nova Canvas aspect_ratio -> (width, height)
    ASPECT_SIZES = {
        "1:1": (1024, 1024), "16:9": (1280, 720), "9:16": (720, 1280),
        "3:2": (1152, 768), "2:3": (768, 1152), "4:3": (1152, 864), "3:4": (864, 1152),
    }

    async def _generate_via_bedrock(self, provider, model_id, prompt, negative_prompt, seed, aspect_ratio, option_params):
        """Generate image via BedrockInvoke (Stability AI / Nova Canvas)"""
        is_nova = 'nova-canvas' in model_id

        if is_nova:
            w, h = self.ASPECT_SIZES.get(aspect_ratio, (1024, 1024))
            request_body = {
                "taskType": "TEXT_IMAGE",
                "textToImageParams": {"text": prompt},
                "imageGenerationConfig": {"width": w, "height": h, "seed": (seed or 0) % 2147483646, "numberOfImages": 1}
            }
            if negative_prompt:
                request_body["textToImageParams"]["negativeText"] = negative_prompt
        else:
            request_body = {
                "mode": "text-to-image",
                "prompt": prompt,
                "negative_prompt": negative_prompt,
                "seed": seed or 0,
                "aspect_ratio": aspect_ratio,
                "output_format": "png"
            }

        if option_params:
            request_body.update(option_params)

        logger.debug(f"[DrawService] Bedrock request: {json.dumps(request_body, indent=2)}")
        response = provider.invoke_model_sync(
            request_body, accept="application/json", content_type="application/json"
        )
        if not response:
            raise ValueError("No response received from model")

        logger.debug(f"[DrawService] Seeds: {response.get('seeds')} Finish: {response.get('finish_reasons')}")
        img_base64 = response["images"][0]
        return Image.open(io.BytesIO(base64.b64decode(img_base64)))

    @staticmethod
    def _extract_image(response) -> Image.Image:
        """Extract image from Gemini response"""
        candidates = response.candidates
        if not candidates or not candidates[0].content or not candidates[0].content.parts:
            raise ValueError("No image returned from Gemini model")
        for part in candidates[0].content.parts:
            if part.inline_data and part.inline_data.mime_type and part.inline_data.mime_type.startswith('image/'):
                return Image.open(io.BytesIO(part.inline_data.data))
        raise ValueError("No image returned from Gemini model")

    async def _generate_via_gemini(self, model_id, prompt, negative_prompt, aspect_ratio, resolution='1K'):
        """Generate image via Gemini native image generation"""
        from google.genai import types
        from genai.models.providers.google_gemini import GeminiProvider
        from genai.models.providers import LLMParameters

        params = LLMParameters(max_tokens=1024, temperature=0.8)
        gemini = GeminiProvider(model_id=model_id, llm_params=params)

        full_prompt = prompt
        if negative_prompt:
            full_prompt += f"\nAvoid: {negative_prompt}"

        config = types.GenerateContentConfig(
            response_modalities=['TEXT', 'IMAGE'],
            image_config=types.ImageConfig(
                aspect_ratio=aspect_ratio or '1:1',
                image_size=resolution or '1K',
            ),
        )
        response = gemini.client.models.generate_content(
            model=model_id, contents=full_prompt, config=config
        )

        # Extract image from response parts
        return self._extract_image(response)

    async def _edit_via_bedrock(self, provider, model_id, image_data, prompt, aspect_ratio):
        """Edit image via BedrockInvoke (Nova Canvas IMAGE_VARIATION / Stability AI image-to-image)"""
        img_b64 = base64.b64encode(image_data).decode('utf-8')
        is_nova = 'nova-canvas' in model_id

        if is_nova:
            w, h = self.ASPECT_SIZES.get(aspect_ratio, (1024, 1024))
            request_body = {
                "taskType": "IMAGE_VARIATION",
                "imageVariationParams": {
                    "images": [img_b64],
                    "text": prompt,
                    "similarityStrength": 0.6,
                },
                "imageGenerationConfig": {"width": w, "height": h, "numberOfImages": 1}
            }
        else:
            # Stability AI image-to-image
            request_body = {
                "mode": "image-to-image",
                "prompt": prompt,
                "image": img_b64,
                "strength": 0.65,
                "output_format": "png"
            }

        logger.debug(f"[DrawService] Bedrock edit request: model={model_id}")
        response = provider.invoke_model_sync(
            request_body, accept="application/json", content_type="application/json"
        )
        if not response:
            raise ValueError("No response received from model")

        img_base64 = response["images"][0]
        return Image.open(io.BytesIO(base64.b64decode(img_base64)))

    async def _edit_via_gemini(self, model_id, image_data, prompt, aspect_ratio, resolution='1K'):
        """Edit image via Gemini — send image + text prompt"""
        from google.genai import types
        from genai.models.providers.google_gemini import GeminiProvider
        from genai.models.providers import LLMParameters

        params = LLMParameters(max_tokens=1024, temperature=0.8)
        gemini = GeminiProvider(model_id=model_id, llm_params=params)

        config = types.GenerateContentConfig(
            response_modalities=['TEXT', 'IMAGE'],
            image_config=types.ImageConfig(
                aspect_ratio=aspect_ratio or '1:1',
                image_size=resolution or '1K',
            ),
        )
        image_part = types.Part.from_bytes(data=image_data, mime_type='image/png')
        response = gemini.client.models.generate_content(
            model=model_id, contents=[image_part, prompt], config=config
        )

        return self._extract_image(response)

    async def edit_image(
        self,
        image_data: bytes,
        prompt: str,
        aspect_ratio: str,
        model_id: Optional[str] = None,
        resolution: str = '1K'
    ) -> Image.Image:
        """Edit image using text instruction"""
        model_id = model_id or module_config.get_default_model(self.module_name)
        if not model_id:
            raise ValueError(f"No default model configured for {self.module_name}")

        model = model_manager.get_model_by_id(model_id)
        if not model:
            raise ValueError(f"Model not found: {model_id}")

        self._validate_model(model_id, model.api_provider)

        if model.api_provider == 'Gemini':
            return await self._edit_via_gemini(model_id, image_data, prompt, aspect_ratio, resolution)
        else:
            provider = self._get_creative_provider(model_id)
            return await self._edit_via_bedrock(provider, model_id, image_data, prompt, aspect_ratio)

    async def text_to_image_stateless(
        self,
        prompt: str,
        negative_prompt: str,
        seed: int,
        aspect_ratio: str,
        option_params: Optional[Dict[str, Any]] = None,
        model_id: Optional[str] = None,
        resolution: str = '1K'
    ) -> Image.Image:
        """Generate image using the configured LLM without session context"""
        try:
            model_id = model_id or module_config.get_default_model(self.module_name)
            if not model_id:
                raise ValueError(f"No default model configured for {self.module_name}")

            model = model_manager.get_model_by_id(model_id)
            if not model:
                raise ValueError(f"Model not found: {model_id}")

            api_provider = model.api_provider
            self._validate_model(model_id, api_provider)

            if api_provider == 'Gemini':
                return await self._generate_via_gemini(model_id, prompt, negative_prompt, aspect_ratio, resolution)
            else:
                provider = self._get_creative_provider(model_id)
                return await self._generate_via_bedrock(provider, model_id, prompt, negative_prompt, seed, aspect_ratio, option_params)

        except LLMProviderError as e:
            logger.error(f"[DrawService] Failed to generate image: {e.error_code}")
            raise

    async def text_to_image(
        self,
        session: Session,
        prompt: str,
        negative_prompt: str,
        seed: int,
        aspect_ratio: str,
        option_params: Optional[Dict[str, Any]] = None
    ) -> Image.Image:
        """Generate image using the configured model"""
        try:
            model_id = await self.get_session_model(session)
            model = model_manager.get_model_by_id(model_id)
            if not model:
                raise ValueError(f"Model not found: {model_id}")

            api_provider = model.api_provider
            self._validate_model(model_id, api_provider)

            if api_provider == 'Gemini':
                return await self._generate_via_gemini(model_id, prompt, negative_prompt, aspect_ratio)
            else:
                provider = self._get_creative_provider(model_id)
                return await self._generate_via_bedrock(provider, model_id, prompt, negative_prompt, seed, aspect_ratio, option_params)

        except LLMProviderError as e:
            logger.error(f"[DrawService] Failed to generate image: {e.error_code}")
            raise
