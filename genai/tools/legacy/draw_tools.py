"""Tools for image generation - Direct Provider approach"""
import io
import json
import base64
import time
import random
from pathlib import Path
from typing import Dict
from PIL import Image
from core.logger import logger
# Delay imports to avoid circular dependencies
from modules.draw.prompts import NEGATIVE_PROMPTS


def generate_image(
    prompt: str,
    negative_prompt: str = '',
    aspect_ratio: str = '16:9',
    **kwargs  # Handle any additional parameters from the schema
) -> Dict:
    """Generate an image from text description using direct provider approach
    
    Args:
        prompt: Text description of the image to generate
        negative_prompt: Optional text describing what to avoid
        aspect_ratio: The aspect ratio of the generated image
        
    Returns:
        Dict containing image path and metadata
    """
    try:
        # Validate prompt
        if not prompt:
            raise ValueError("Prompt is required")

        # Import dependencies dynamically to avoid circular imports
        from genai.models.model_manager import model_manager
        from genai.models import GenImageParameters
        models = model_manager.get_models(filter={'category': 'image'})
        if not models:
            raise ValueError("No image generation models available")
        
        # Find Stability AI model
        stability_model = None
        for model in models:
            if 'stability' in model.model_id:
                stability_model = model
                break
        
        if not stability_model:
            raise ValueError("No Stability AI image generation models available")
        
        logger.debug(f"[generate_image] Using model: {stability_model.model_id}")

        # Create image generation parameters
        gen_params = GenImageParameters(
            width=1024,
            height=1024,
            aspect_ratio=aspect_ratio
        )

        # Import provider dynamically to avoid circular imports
        from genai.models.providers.bedrock_invoke import BedrockInvoke
        
        # Create provider instance
        provider = BedrockInvoke(stability_model.model_id, gen_params)

        # Prepare negative prompts
        negative_prompts = NEGATIVE_PROMPTS.copy()
        if negative_prompt:
            negative_prompts.append(negative_prompt)

        # Generate a random seed for reproducibility
        used_seed = random.randrange(0, 4294967295)

        # Prepare request body (following draw_service pattern)
        request_body = {
            "mode": "text-to-image",
            "prompt": prompt,
            "negative_prompt": "\n".join(negative_prompts),
            "seed": used_seed,
            "aspect_ratio": aspect_ratio,
            "output_format": "png"
        }

        logger.debug(f"[generate_image] Request body: {json.dumps(request_body, indent=2)}")

        # Generate image using provider's direct invoke method
        response = provider.invoke_model_sync(
            request_body=request_body,
            accept="application/json",
            content_type="application/json"
        )

        if not response:
            raise ValueError("No response received from model")

        logger.debug(f"[generate_image] Generation completed - Seeds: {response.get('seeds')}")

        # Convert base64 to image (following draw_service pattern)
        img_base64 = response["images"][0]
        image = Image.open(io.BytesIO(base64.b64decode(img_base64)))

        # Save to project's assets directory
        images_dir = Path("assets/generated/images")
        images_dir.mkdir(parents=True, exist_ok=True)

        # Create a unique filename with timestamp and seed
        timestamp = int(time.time())
        filename = f"img_{timestamp}_{used_seed}.png"
        file_path = images_dir / filename

        # Save the image
        image.save(file_path, format="PNG")

        logger.info(f"[generate_image] Image saved to: {file_path}")

        # Return the file path and metadata with success status
        return {
            "status": "success",
            "file_path": str(file_path),
            "metadata": {
                "seed": used_seed,
                "aspect_ratio": aspect_ratio,
                "model": stability_model.model_id,
                "prompt": prompt,
                "seeds": response.get('seeds'),
                "finish_reasons": response.get('finish_reasons')
            }
        }
        
    except ValueError as e:
        logger.error(f"[generate_image] Validation error: {str(e)}")
        return {"status": "error", "error": f"Validation error: {str(e)}"}
    except ImportError as e:
        logger.error(f"[generate_image] Import error: {str(e)}")
        return {"status": "error", "error": "Image generation provider not available"}
    except Exception as e:
        logger.error(f"[generate_image] Unexpected error: {str(e)}", exc_info=True)
        return {"status": "error", "error": f"Image generation failed: {str(e)}"}


# Tool specifications in Bedrock format
list_of_tools_specs = [
    {
        "toolSpec": {
            "name": "generate_image",
            "description": "Generate image from a text description using Stable Diffusion model.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "prompt": {
                            "type": "string",
                            "description": "Stable Diffusion prompt written in English that specifies the content and style for the generated image."
                        },
                        "negative_prompt": {
                            "type": "string",
                            "description": "Optional keywords of what you do not wish to see in the output image",
                            "default": ""
                        },
                        "aspect_ratio": {
                            "type": "string",
                            "description": "Desired aspect ratio in 'width:height' format (e.g., '16:9', '5:4', '3:2', '21:9', '1:1', '2:3', '4:5', '9:16', '9:21'). If provided, height will be calculated based on the width.",
                            "default": '16:9'
                        }
                    },
                    "required": ["prompt"]
                }
            }
        }
    }
]
